# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""The embeddings job an import queues once it is done."""

import json
from pathlib import Path

import psycopg
import pytest

from pixano.api.jobs import follow_ups as follow_ups_module
from pixano.api.jobs.follow_ups import (
    EMBEDDINGS_KIND,
    EMBEDDINGS_UNREADABLE,
    NO_IMAGE,
    NO_MODEL,
    NO_WORKER,
    QUEUE_UNREADABLE,
    asks_for_embeddings,
    considers_embeddings,
    decide_embeddings,
    embeddings_unavailable,
    plan_has_still_images,
    submit_follow_ups,
)
from pixano.datasets import Dataset
from pixano.datasets.dataset_info import DatasetInfo
from pixano.datasets.io.jobs import FollowUp
from pixano.schemas import Image, Record, SequenceFrame, Text, Video
from tests.fixtures.job_queue import queued_jobs


# The embeddings of a model the import named, and of one the deployment chose.
EMBEDDINGS = FollowUp(kind=EMBEDDINGS_KIND, params={"model": "clip"})
DEFAULT_EMBEDDINGS = FollowUp(kind=EMBEDDINGS_KIND, params={"model": "clip"}, defaulted=("model",))


def _dataset(library: Path, views: dict) -> Dataset:
    """A dataset as an import leaves it, with the views given."""
    return Dataset.create(library / "photos", DatasetInfo(id="photos", name="Photos", record=Record, views=views))


class TestWhatAnImportAsks:
    @pytest.mark.parametrize(
        ("compute", "model", "asked"),
        [(None, None, None), (None, "clip", True), (False, "clip", False), (True, None, True)],
        ids=["says nothing", "names a model", "says no", "says yes"],
    )
    def test_a_named_model_asks_for_the_embeddings(self, compute: bool | None, model: str | None, asked) -> None:
        assert asks_for_embeddings(compute, model) is asked

    @pytest.mark.parametrize(
        ("wanted", "default_on", "has_images", "considered"),
        [
            (True, False, False, True),
            (False, True, True, False),
            (None, True, None, True),
            (None, True, True, True),
            (None, True, False, False),
            (None, False, True, False),
        ],
        ids=["asked", "refused", "default, plan unknown", "default, images", "default, no image", "default off"],
    )
    def test_the_default_leaves_out_an_import_whose_plan_holds_no_image(
        self, wanted: bool | None, default_on: bool, has_images: bool | None, considered: bool
    ) -> None:
        """An import of text or video, by default, must not read a refusal."""
        assert considers_embeddings(wanted, default_on=default_on, has_images=has_images) is considered

    @pytest.mark.parametrize(
        ("schema", "has_images"),
        [
            ({"views": {"image": {"base": "Image"}}}, True),
            ({"views": {"video": {"base": "Video"}, "frames": {"base": "SequenceFrame"}}}, False),
            ({"views": {}}, False),
            ({"record": {"base": "Record"}}, None),
            (None, None),
        ],
        ids=["images", "a video's frames", "no view", "views unsaid", "no schema"],
    )
    def test_a_plan_says_whether_it_holds_still_images(self, schema, has_images: bool | None) -> None:
        assert plan_has_still_images(schema) is has_images


class TestDecidingEmbeddings:
    """What an import asks for, from its request, the deployment's default and the queue's state."""

    def test_asked_off_none(self) -> None:
        assert decide_embeddings(False, "clip", named=True, default_on=True, unavailable=None) == []

    def test_by_default_where_the_job_can_run(self) -> None:
        assert decide_embeddings(None, "clip", named=False, default_on=True, unavailable=None) == [DEFAULT_EMBEDDINGS]

    def test_a_model_the_import_named_is_kept_as_named(self) -> None:
        assert decide_embeddings(None, "clip", named=True, default_on=True, unavailable=None) == [EMBEDDINGS]

    @pytest.mark.parametrize(
        ("model", "default_on", "unavailable"),
        [("clip", False, None), ("clip", True, NO_WORKER), (None, True, None)],
        ids=["default off", "job cannot run", "no model"],
    )
    def test_the_default_asks_nothing_where_the_job_cannot_run(
        self, model: str | None, default_on: bool, unavailable: str | None
    ) -> None:
        """An installation without jobs must not read a refusal after every import."""
        assert decide_embeddings(None, model, named=False, default_on=default_on, unavailable=unavailable) == []

    def test_asked_for_it_is_kept_whatever_the_queue_says(self) -> None:
        """The import then says why it was not queued, if it is not."""
        assert decide_embeddings(True, "clip", named=True, default_on=False, unavailable=NO_WORKER) == [EMBEDDINGS]

    def test_asked_for_without_a_model_says_so_at_once(self) -> None:
        assert decide_embeddings(True, None, named=False, default_on=True, unavailable=None) == [
            FollowUp(kind=EMBEDDINGS_KIND, error=f"not queued: {NO_MODEL}")
        ]

    def test_what_to_say_without_a_model_is_the_callers(self) -> None:
        """The CLI asks no inference: it names its own options."""
        (follow_up,) = decide_embeddings(
            True, None, named=False, default_on=True, unavailable=None, no_model="pass a model"
        )

        assert follow_up.error == "not queued: pass a model"


class TestWhetherTheJobCanRun:
    def test_without_a_queue_configured_it_says_what_to_set(self) -> None:
        assert "PIXANO_DATABASE_URL" in (embeddings_unavailable(None) or "")

    def test_an_unreachable_queue_says_so_without_its_address_or_password(self) -> None:
        """Read by every client that opens the import form, and kept on the import's job."""
        unreachable = "postgresql://nobody:secret@127.0.0.1:1/none?connect_timeout=1"

        assert embeddings_unavailable(unreachable) == QUEUE_UNREADABLE

    def test_a_queue_that_fails_once_connected_says_so_and_raises_nothing(
        self, queue_url: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A role without the rights, a server restarting: an import must not fail for it."""

        def failing(conn: psycopg.Connection) -> None:
            raise psycopg.errors.InsufficientPrivilege("permission denied for schema pixano_jobs")

        monkeypatch.setattr(follow_ups_module, "available_kinds", failing)

        assert embeddings_unavailable(queue_url) == QUEUE_UNREADABLE

    def test_a_queue_no_worker_declared_it_on(self, queue_url: str) -> None:
        assert embeddings_unavailable(queue_url) == NO_WORKER

    def test_a_queue_a_worker_declared_it_on(self, embeddings_declared: str) -> None:
        assert embeddings_unavailable(embeddings_declared) is None

    def test_the_queues_statements_and_locks_are_bounded(
        self, embeddings_declared: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A queue being reinstalled must not hold an import, nor the import runner behind it."""
        bounds: list[tuple] = []
        available_kinds = follow_ups_module.available_kinds

        def recording(conn: psycopg.Connection) -> dict:
            bounds.append(
                (
                    conn.execute("SHOW statement_timeout").fetchone(),
                    conn.execute("SHOW lock_timeout").fetchone(),
                )
            )
            return available_kinds(conn)

        monkeypatch.setattr(follow_ups_module, "available_kinds", recording)

        embeddings_unavailable(embeddings_declared)

        assert bounds == [(("5s",), ("5s",))]


class TestStartingTheEmbeddings:
    def test_it_is_queued_on_the_imported_dataset(self, embeddings_declared: str, tmp_path: Path) -> None:
        _dataset(tmp_path, {"image": Image})

        [(outcome,)] = submit_follow_ups(embeddings_declared, tmp_path, "photos", [EMBEDDINGS])

        assert outcome.job_id and not outcome.error
        assert queued_jobs(embeddings_declared) == [(EMBEDDINGS_KIND, "photos", {"model": "clip"})]

    def test_every_model_the_dataset_holds_is_computed_again_beside_the_one_named(
        self, embeddings_declared: str, tmp_path: Path
    ) -> None:
        """The media an import added are in none of their embeddings: one job per model, the one named first."""
        dataset = _dataset(tmp_path, {"image": Image})
        dataset.create_record_embedding_table(dim=4, model_id="siglip")
        dataset.create_record_embedding_table(dim=8, model_id="dinov2", checkpoint="vitb14")

        [outcomes] = submit_follow_ups(embeddings_declared, tmp_path, "photos", [EMBEDDINGS])

        assert [(outcome.params, bool(outcome.job_id), outcome.error) for outcome in outcomes] == [
            ({"model": "clip"}, True, ""),
            ({"model": "siglip"}, True, ""),
            ({"model": "dinov2"}, True, ""),
        ]
        assert queued_jobs(embeddings_declared) == [
            (EMBEDDINGS_KIND, "photos", {"model": "clip"}),
            (EMBEDDINGS_KIND, "photos", {"model": "siglip"}),
            (EMBEDDINGS_KIND, "photos", {"model": "dinov2"}),
        ]

    def test_a_model_held_is_computed_once_whatever_its_checkpoints(
        self, embeddings_declared: str, tmp_path: Path
    ) -> None:
        """A job computes the checkpoint the inference serves under the name: one per name."""
        dataset = _dataset(tmp_path, {"image": Image})
        dataset.create_record_embedding_table(dim=4, model_id="clip", checkpoint="MobileCLIP2-S2")
        dataset.create_record_embedding_table(dim=8, model_id="clip", checkpoint="ViT-L-14")
        siglip = FollowUp(kind=EMBEDDINGS_KIND, params={"model": "siglip"})

        [outcomes] = submit_follow_ups(embeddings_declared, tmp_path, "photos", [siglip])

        assert [outcome.params for outcome in outcomes] == [{"model": "siglip"}, {"model": "clip"}]

    def test_a_model_the_deployment_chose_stands_in_only_for_a_dataset_without_embeddings(
        self, embeddings_declared: str, tmp_path: Path
    ) -> None:
        """Chosen by no one, it would add a model, computed over the whole dataset, to every import."""
        dataset = _dataset(tmp_path, {"image": Image})
        dataset.create_record_embedding_table(dim=4, model_id="siglip")

        [outcomes] = submit_follow_ups(embeddings_declared, tmp_path, "photos", [DEFAULT_EMBEDDINGS])

        assert [(outcome.params, bool(outcome.job_id)) for outcome in outcomes] == [({"model": "siglip"}, True)]
        assert queued_jobs(embeddings_declared) == [(EMBEDDINGS_KIND, "photos", {"model": "siglip"})]

    def test_a_model_the_deployment_chose_is_computed_on_a_dataset_without_embeddings(
        self, embeddings_declared: str, tmp_path: Path
    ) -> None:
        _dataset(tmp_path, {"image": Image})

        [(outcome,)] = submit_follow_ups(embeddings_declared, tmp_path, "photos", [DEFAULT_EMBEDDINGS])

        assert outcome.params == {"model": "clip"} and outcome.job_id

    def test_a_model_held_without_a_name_cannot_be_asked_for(self, embeddings_declared: str, tmp_path: Path) -> None:
        """A description written before models had names: no job can name it."""
        dataset = _dataset(tmp_path, {"image": Image})
        dataset.create_record_embedding_table(dim=4, model_id="")

        [(outcome,)] = submit_follow_ups(embeddings_declared, tmp_path, "photos", [DEFAULT_EMBEDDINGS])

        assert outcome.params == {"model": "clip"} and outcome.job_id

    def test_a_description_that_cannot_be_read_entirely_takes_no_job(
        self, embeddings_declared: str, tmp_path: Path
    ) -> None:
        """The worker would refuse each, one failed job per model for one cause."""
        dataset = _dataset(tmp_path, {"image": Image})
        dataset.create_record_embedding_table(dim=4, model_id="siglip")
        sidecar = dataset.path / "embeddings.json"
        document = json.loads(sidecar.read_text())
        sidecar.write_text(json.dumps({**document, "version": 99}))

        [(outcome,)] = submit_follow_ups(embeddings_declared, tmp_path, "photos", [EMBEDDINGS])

        assert outcome.error == f"not queued: {EMBEDDINGS_UNREADABLE}"
        assert queued_jobs(embeddings_declared) == []

    @pytest.mark.parametrize(
        "views", [{"text": Text}, {"video": Video, "frames": SequenceFrame}], ids=["text", "a video's frames"]
    )
    def test_a_dataset_without_a_still_image_queues_nothing(
        self, embeddings_declared: str, tmp_path: Path, views: dict
    ) -> None:
        _dataset(tmp_path, views)

        [(outcome,)] = submit_follow_ups(embeddings_declared, tmp_path, "photos", [EMBEDDINGS])

        assert outcome.error == f"not queued: {NO_IMAGE}" and not outcome.job_id
        assert queued_jobs(embeddings_declared) == []

    def test_a_follow_up_with_nothing_to_do_says_so_whatever_the_queue(self, tmp_path: Path) -> None:
        """Fitted first: without a queue, the dataset's lack of an image is still the reason given."""
        _dataset(tmp_path, {"text": Text})

        [(outcome,)] = submit_follow_ups(None, tmp_path, "photos", [EMBEDDINGS])

        assert outcome.error == f"not queued: {NO_IMAGE}"

    def test_a_queue_that_fails_while_queueing_rolls_them_all_back_and_says_so(
        self, embeddings_declared: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _dataset(tmp_path, {"image": Image})
        submit = follow_ups_module.submit
        calls: list[str] = []

        def failing_second(conn: psycopg.Connection, **kwargs) -> object:
            calls.append(kwargs["kind"])
            if len(calls) == 2:
                raise psycopg.errors.QueryCanceled("canceling statement due to statement timeout")
            return submit(conn, **kwargs)

        monkeypatch.setattr(follow_ups_module, "submit", failing_second)

        outcomes = submit_follow_ups(embeddings_declared, tmp_path, "photos", [EMBEDDINGS, EMBEDDINGS])

        assert [outcome.error for became in outcomes for outcome in became] == [f"not queued: {QUEUE_UNREADABLE}"] * 2
        assert queued_jobs(embeddings_declared) == [], "the first one is rolled back with the second"

    def test_the_jobs_of_one_follow_up_are_queued_together_or_not_at_all(
        self, embeddings_declared: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        dataset = _dataset(tmp_path, {"image": Image})
        dataset.create_record_embedding_table(dim=4, model_id="siglip")
        dataset.create_record_embedding_table(dim=8, model_id="dinov2")
        submit = follow_ups_module.submit
        calls: list[str] = []

        def failing_second(conn: psycopg.Connection, **kwargs) -> object:
            calls.append(kwargs["params"]["model"])
            if len(calls) == 2:
                raise psycopg.errors.QueryCanceled("canceling statement due to statement timeout")
            return submit(conn, **kwargs)

        monkeypatch.setattr(follow_ups_module, "submit", failing_second)

        [outcomes] = submit_follow_ups(embeddings_declared, tmp_path, "photos", [EMBEDDINGS])

        assert [(outcome.params["model"], outcome.error) for outcome in outcomes] == [
            ("clip", f"not queued: {QUEUE_UNREADABLE}"),
            ("siglip", f"not queued: {QUEUE_UNREADABLE}"),
            ("dinov2", f"not queued: {QUEUE_UNREADABLE}"),
        ]
        assert queued_jobs(embeddings_declared) == []

    def test_a_dataset_not_in_the_library_is_raised(self, embeddings_declared: str, tmp_path: Path) -> None:
        """The import engine turns it into a reason for each follow-up (`queue_follow_ups`)."""
        with pytest.raises(FileNotFoundError):
            submit_follow_ups(embeddings_declared, tmp_path, "nowhere", [EMBEDDINGS])

    def test_a_queue_no_worker_declared_it_on_says_so(self, queue_url: str, tmp_path: Path) -> None:
        _dataset(tmp_path, {"image": Image})

        [(outcome,)] = submit_follow_ups(queue_url, tmp_path, "photos", [EMBEDDINGS])

        assert outcome.error.startswith("not queued: no worker has declared the job kind 'embeddings'")
        assert queued_jobs(queue_url) == []

    def test_without_a_queue_each_says_what_to_set(self, tmp_path: Path) -> None:
        _dataset(tmp_path, {"image": Image})

        [(outcome,)] = submit_follow_ups(None, tmp_path, "photos", [EMBEDDINGS])

        assert outcome.error.startswith("not queued: no job queue is configured")
