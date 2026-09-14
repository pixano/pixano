# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Tests for the job event stream."""

import asyncio
import json
import os

import psycopg
import pytest
from fastapi import HTTPException
from psycopg.types.json import Jsonb

from pixano.api.jobs import SCHEMA_NAME
from pixano.api.jobs.events import NOTIFY_CHANNEL, EventBroker, JobEvent, read_since
from pixano.api.routers.jobs import _requested_types


TEST_DATABASE_URL = "PIXANO_TEST_DATABASE_URL"


@pytest.fixture
def url() -> str:
    """A throwaway queue, emptied around each test."""
    value = os.environ.get(TEST_DATABASE_URL, "")
    if not value:
        pytest.skip(f"{TEST_DATABASE_URL} not set")
    with psycopg.connect(value, autocommit=True) as conn:
        exists = conn.execute(f"SELECT to_regclass('{SCHEMA_NAME}.jobs')").fetchone()
        if exists is None or exists[0] is None:
            pytest.skip("the queue schema is absent — pixano-worker installs it")
        conn.execute(f"TRUNCATE {SCHEMA_NAME}.jobs CASCADE")
    yield value
    with psycopg.connect(value, autocommit=True) as conn:
        conn.execute(f"TRUNCATE {SCHEMA_NAME}.jobs CASCADE")


def _job_with_events(url: str, count: int) -> tuple[str, list[int]]:
    """A job carrying `count` progress events, and their identifiers."""
    with psycopg.connect(url, autocommit=True) as conn:
        row = conn.execute(
            f"INSERT INTO {SCHEMA_NAME}.jobs (kind, dataset, total_tasks) " "VALUES ('fake', 'ds', 100) RETURNING id"
        ).fetchone()
        assert row is not None
        job = str(row[0])
        ids = []
        for done in range(1, count + 1):
            event = conn.execute(
                f"INSERT INTO {SCHEMA_NAME}.job_events (job_id, type, payload) "
                "VALUES (%s, 'progress', %s) RETURNING id",
                (job, Jsonb({"done_tasks": done * 10, "total_tasks": 100})),
            ).fetchone()
            assert event is not None
            ids.append(event[0])
    return job, ids


class TestRendering:
    """The wire format is what a browser's EventSource parses."""

    def test_carries_the_identifier_so_a_client_can_resume(self) -> None:
        rendered = JobEvent(id=42, job_id="j", type="progress", payload={"done_tasks": 20}).to_sse()

        assert rendered.startswith("id: 42\n")
        assert "event: progress\n" in rendered
        assert rendered.endswith("\n\n"), "un message SSE se termine par une ligne vide"

    def test_the_body_names_its_job(self) -> None:
        """Le flux global mélange les jobs : sans cet identifiant il serait illisible."""
        rendered = JobEvent(id=1, job_id="abc", type="state", payload={"state": "done"}).to_sse()

        body = json.loads(rendered.split("data: ", 1)[1])
        assert body == {"job_id": "abc", "state": "done"}


class TestCatchUp:
    def test_reads_only_what_came_after(self, url: str) -> None:
        job, ids = _job_with_events(url, 5)

        missed = asyncio.run(read_since(url, job, ids[1]))

        assert [event.id for event in missed] == ids[2:]

    def test_a_fresh_client_gets_everything(self, url: str) -> None:
        job, ids = _job_with_events(url, 3)

        assert [event.id for event in asyncio.run(read_since(url, job, 0))] == ids

    def test_another_job_is_not_mixed_in(self, url: str) -> None:
        job, _ = _job_with_events(url, 2)
        other, _ = _job_with_events(url, 2)

        missed = asyncio.run(read_since(url, job, 0))

        assert {event.job_id for event in missed} == {job}


class TestBroker:
    def test_no_configured_queue_makes_it_inert(self) -> None:
        """Une application sans file ne doit pas planter au démarrage, juste ne rien diffuser."""
        assert EventBroker(None).enabled is False

    def test_delivers_an_event_to_a_matching_stream(self, url: str) -> None:
        job, _ = _job_with_events(url, 0)

        async def scenario() -> JobEvent:
            broker = EventBroker(url)
            broker.start()
            try:
                async with broker.subscribe(job_id=job) as subscriber:
                    await asyncio.sleep(1.0)  # laisser l'écoute s'établir
                    _emit(url, job, "progress", {"done_tasks": 30, "total_tasks": 100})
                    return await asyncio.wait_for(subscriber.queue.get(), timeout=5)
            finally:
                await broker.stop()

        event = asyncio.run(scenario())
        assert event.job_id == job
        assert event.payload["done_tasks"] == 30

    def test_ignores_another_job(self, url: str) -> None:
        """Deux flux ouverts sur deux jobs ne doivent pas se contaminer."""
        watched, _ = _job_with_events(url, 0)
        other, _ = _job_with_events(url, 0)

        async def scenario() -> bool:
            broker = EventBroker(url)
            broker.start()
            try:
                async with broker.subscribe(job_id=watched) as subscriber:
                    await asyncio.sleep(1.0)
                    _emit(url, other, "progress", {"done_tasks": 10, "total_tasks": 100})
                    try:
                        await asyncio.wait_for(subscriber.queue.get(), timeout=2)
                        return False
                    except asyncio.TimeoutError:
                        return True
            finally:
                await broker.stop()

        assert asyncio.run(scenario()), "un événement d'un autre job a fuité dans le flux"

    def test_a_filtered_stream_only_hears_state_changes(self, url: str) -> None:
        """C'est ce qui évite de noyer la liste des jobs sous la progression."""
        job, _ = _job_with_events(url, 0)

        async def scenario() -> JobEvent:
            broker = EventBroker(url)
            broker.start()
            try:
                async with broker.subscribe(types=frozenset({"state"})) as subscriber:
                    await asyncio.sleep(1.0)
                    _emit(url, job, "progress", {"done_tasks": 10, "total_tasks": 100})
                    _emit(url, job, "state", {"state": "done"})
                    return await asyncio.wait_for(subscriber.queue.get(), timeout=5)
            finally:
                await broker.stop()

        assert asyncio.run(scenario()).type == "state"


def _emit(url: str, job_id: str, event_type: str, payload: dict) -> None:
    """Write an event and ring the bell, the way the worker does."""
    with psycopg.connect(url, autocommit=True) as conn:
        conn.execute(
            f"""
            WITH inserted AS (
                INSERT INTO {SCHEMA_NAME}.job_events (job_id, type, payload)
                VALUES (%s, %s, %s) RETURNING id, job_id, type
            )
            SELECT pg_notify(%s, json_build_object(
                'job_id', job_id, 'event_id', id, 'type', type)::text) FROM inserted
            """,
            (job_id, event_type, Jsonb(payload), NOTIFY_CHANNEL),
        )


class TestTypeFilter:
    """Le client dit ce qu'il veut entendre — le serveur refuse ce qu'il ne comprend pas."""

    def test_no_filter_means_everything(self) -> None:
        assert _requested_types(None) is None

    def test_a_single_type_is_kept(self) -> None:
        assert _requested_types("state") == frozenset({"state"})

    def test_spaces_around_names_are_tolerated(self) -> None:
        assert _requested_types(" state , progress ") == frozenset({"state", "progress"})

    def test_an_empty_filter_means_everything(self) -> None:
        assert _requested_types("") is None

    def test_an_unknown_type_is_refused_rather_than_ignored(self) -> None:
        """Ignorer `stat` produirait un flux muet, et le silence est le pire des diagnostics."""
        with pytest.raises(HTTPException) as raised:
            _requested_types("stat")

        assert raised.value.status_code == 422
        assert "stat" in raised.value.detail
        assert "progress" in raised.value.detail, "le message doit nommer les valeurs acceptées"
