# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""The NER kind: which mentions it keeps, what it does with each failure, and what it leaves to the
spans a person drew or accepted."""

import io
import json
from types import SimpleNamespace
from typing import Any

import pytest
from pixano_inference.client import PixanoInferenceError
from pixano_worker.kinds import MODEL_TASK_MARKER, NerKind, TransientError
from pixano_worker.kinds.ner import (
    TEXT_FILE_NOT_FOUND,
    TEXT_FILE_UNREADABLE,
    TEXT_NOT_HELD,
    TEXT_NOT_UTF8,
    WITNESS_TEXT,
)
from pixano_worker.progress import ChunkCancelled, ChunkProgress
from pixano_worker.writer import JobWriter, ModelIdentity

from pixano.schemas import Entity, Text


SENTENCE = "Ada Lovelace met Charles Babbage in London."
# The offsets of its mentions in the sentence.
ADA = (0, 12)
BABBAGE = (17, 32)
LONDON = (36, 42)


def _entity(span: tuple[int, int], label: str, score: float = 0.9, text: str = "") -> Any:
    start, end = span
    return SimpleNamespace(text=text or SENTENCE[start:end], label=label, start=start, end=end, score=score)


class _Inference:
    """An inference that answers, for each text, the entities a test gave it."""

    def __init__(self) -> None:
        self.answers: dict[str, list[Any]] = {}
        self.bad: set[str] = set()
        self.status_for_everything: int | None = None
        self.calls: list[Any] = []
        self.opened = self.closed = 0

    def client(self, *_args: Any, **_kwargs: Any) -> "_Inference":
        self.opened += 1
        return self

    def __enter__(self) -> "_Inference":
        return self

    def __exit__(self, *_exc: Any) -> None:
        self.closed += 1

    def list_models(self) -> list[Any]:
        return [SimpleNamespace(name="fake-ner", model_path="", capability="ner")]

    def ner(self, request: Any, **_kwargs: Any) -> Any:
        self.calls.append(request)
        if self.status_for_everything is not None:
            raise PixanoInferenceError(self.status_for_everything, "error", "refused")
        if request.text in self.bad:
            raise PixanoInferenceError(500, "internal_error", "Inference error.")
        return SimpleNamespace(data=SimpleNamespace(entities=self.answers.get(request.text, [])))


class _Reader:
    """Texts, some missing, some empty, some held by a URI alone: a file this worker reads, or not."""

    def __init__(
        self,
        texts: dict[str, str],
        tables: dict[str, Any] | None = None,
        uris: dict[str, str] | None = None,
        files: dict[str, bytes] | None = None,
        progress: ChunkProgress | None = None,
    ) -> None:
        self.texts = texts
        self.uris = uris or {}
        self.files = files or {}
        self.progress = progress if progress is not None else ChunkProgress(0)
        self.dataset = SimpleNamespace(
            info=SimpleNamespace(tables=tables if tables is not None else {"texts": Text, "entities": Entity})
        )

    def open_media(self, table_name: str, view: Any) -> Any:
        found = self.files.get(view.uri)
        return None if found is None else io.BytesIO(found)

    def media_tables(self, media_type: str) -> list[str]:
        return ["texts"] if media_type == "text" and "texts" in self.dataset.info.tables else []

    def ids(self, table_name: str) -> list[str]:
        return list(self.texts)

    def rows(self, table_name: str, ids: list[str]) -> list[Any]:
        return [
            SimpleNamespace(
                id=view_id, record_id=f"rec-{view_id}", content=self.texts[view_id], uri=self.uris.get(view_id, "")
            )
            for view_id in ids
            if view_id in self.texts
        ]


@pytest.fixture
def inference(monkeypatch: pytest.MonkeyPatch) -> _Inference:
    fake = _Inference()
    monkeypatch.setattr("pixano_worker.kinds.inference.SyncPixanoInferenceClient", fake.client)
    return fake


KIND = NerKind("http://inference", "")
PARAMS = KIND.validate_params({"model": "fake-ner"})


def _process(reader: _Reader, view_ids: list[str], params: Any = PARAMS) -> tuple[dict[str, Any], Any]:
    payload = {"table": "texts", "view_ids": view_ids}
    result = KIND.process(reader, payload, params)  # type: ignore[arg-type]
    return result, KIND.outcome(result, payload, len(view_ids))


class TestParameters:
    def test_names_no_model_and_asks_the_form_for_a_served_one(self) -> None:
        model = KIND.params_schema()["properties"]["model"]

        assert "default" not in model and model[MODEL_TASK_MARKER] == "ner"

    def test_replacing_the_previous_spans_is_confirmed(self) -> None:
        assert "x-pixano-confirm" in KIND.params_schema()["properties"]["replace_previous"]


class TestRecognition:
    def test_each_entity_keeps_its_class_and_its_offsets_in_the_text(self, inference: _Inference) -> None:
        inference.answers[SENTENCE] = [_entity(ADA, "PER"), _entity(LONDON, "LOC")]

        result, outcome = _process(_Reader({"t1": SENTENCE}), ["t1"])

        assert [(m["text"], m["label"], m["start"], m["end"]) for m in result["texts"][0]["mentions"]] == [
            ("Ada Lovelace", "PER", 0, 12),
            ("London", "LOC", 36, 42),
        ]
        assert (outcome.produced, outcome.skipped, outcome.quarantined) == (1, 0, [])
        assert [call.text for call in inference.calls] == [SENTENCE]

    def test_a_mention_is_the_texts_own_whatever_the_model_says(self, inference: _Inference) -> None:
        inference.answers[SENTENCE] = [_entity(ADA, "PER", text="ada lovelace ")]

        result, _ = _process(_Reader({"t1": SENTENCE}), ["t1"])

        assert result["texts"][0]["mentions"][0]["text"] == "Ada Lovelace"

    def test_offsets_that_place_nothing_in_the_text_are_left_out(self, inference: _Inference) -> None:
        inference.answers[SENTENCE] = [_entity((40, 400), "LOC"), _entity((5, 5), "PER"), _entity((-1, 3), "PER")]

        result, outcome = _process(_Reader({"t1": SENTENCE}), ["t1"])

        assert (result["texts"][0]["mentions"], outcome.produced) == ([], 1)

    def test_only_the_classes_asked_for_are_kept_case_aside(self, inference: _Inference) -> None:
        inference.answers[SENTENCE] = [_entity(ADA, "PER"), _entity(LONDON, "LOC")]

        result, _ = _process(
            _Reader({"t1": SENTENCE}), ["t1"], KIND.validate_params({"model": "fake-ner", "entity_types": ["loc"]})
        )

        assert [m["label"] for m in result["texts"][0]["mentions"]] == ["LOC"]

    def test_an_entity_scored_below_the_threshold_is_left_out(self, inference: _Inference) -> None:
        inference.answers[SENTENCE] = [_entity(ADA, "PER", score=0.4), _entity(BABBAGE, "PER", score=0.6)]

        result, _ = _process(_Reader({"t1": SENTENCE}), ["t1"])

        assert [m["text"] for m in result["texts"][0]["mentions"]] == ["Charles Babbage"]

    def test_offsets_are_kept_as_the_interface_counts_them_past_an_emoji(self, inference: _Inference) -> None:
        """Python counts the emoji as one character, the interface as two UTF-16 code units."""
        text = "\U0001f389 Ada Lovelace"
        inference.answers[text] = [SimpleNamespace(text="Ada Lovelace", label="PER", start=2, end=14, score=0.9)]

        result, _ = _process(_Reader({"t1": text}), ["t1"])

        assert [(m["text"], m["start"], m["end"]) for m in result["texts"][0]["mentions"]] == [("Ada Lovelace", 3, 15)]

    def test_a_mention_returned_twice_is_kept_once(self, inference: _Inference) -> None:
        inference.answers[SENTENCE] = [_entity(ADA, "PER"), _entity(ADA, "PER"), _entity(ADA, "ORG")]

        result, _ = _process(_Reader({"t1": SENTENCE}), ["t1"])

        assert [m["label"] for m in result["texts"][0]["mentions"]] == ["PER", "ORG"]

    def test_the_chunk_says_how_far_it_got_after_each_text(self, inference: _Inference) -> None:
        progress = ChunkProgress(3)

        _process(_Reader({"t1": SENTENCE, "t2": "", "t3": "Grace Hopper"}, progress=progress), ["t1", "t2", "t3"])

        assert progress.done == 3

    def test_a_job_cancelled_meanwhile_stops_before_the_next_text(
        self, inference: _Inference, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        progress = ChunkProgress(2)
        answer = inference.ner

        def answer_then_cancel(request: Any, **kwargs: Any) -> Any:
            progress.cancel()
            return answer(request, **kwargs)

        monkeypatch.setattr(inference, "ner", answer_then_cancel)

        with pytest.raises(ChunkCancelled):
            _process(_Reader({"t1": SENTENCE, "t2": "Grace Hopper"}, progress=progress), ["t1", "t2"])
        assert (len(inference.calls), progress.done) == (1, 1)

    def test_a_text_where_the_model_finds_nothing_is_produced(self, inference: _Inference) -> None:
        _, outcome = _process(_Reader({"t1": "nothing to see here"}), ["t1"])

        assert (outcome.produced, outcome.skipped) == (1, 0)


class TestFailures:
    def test_an_empty_text_is_skipped_without_a_call(self, inference: _Inference) -> None:
        _, outcome = _process(_Reader({"t1": "  "}), ["t1"])

        assert (outcome.produced, outcome.skipped, inference.calls) == (0, 1, [])

    def test_a_text_held_by_its_file_alone_is_read_from_it(self, inference: _Inference) -> None:
        inference.answers[SENTENCE] = [_entity(ADA, "PER")]
        reader = _Reader({"t1": ""}, uris={"t1": "texts/t1.txt"}, files={"texts/t1.txt": SENTENCE.encode()})

        result, outcome = _process(reader, ["t1"])

        assert (outcome.produced, [m["text"] for m in result["texts"][0]["mentions"]]) == (1, ["Ada Lovelace"])

    def test_a_text_at_a_url_this_worker_does_not_read_is_quarantined_not_skipped(self, inference: _Inference) -> None:
        _, outcome = _process(_Reader({"t1": ""}, uris={"t1": "https://example.org/t1.txt"}), ["t1"])

        assert (outcome.skipped, [(item.item_id, item.reason) for item in outcome.quarantined]) == (
            0,
            [("t1", TEXT_NOT_HELD)],
        )
        assert inference.calls == []

    def test_a_text_file_missing_from_the_media_root_is_quarantined_as_not_found(self, inference: _Inference) -> None:
        _, outcome = _process(_Reader({"t1": ""}, uris={"t1": "texts/gone.txt"}), ["t1"])

        assert [item.reason for item in outcome.quarantined] == [TEXT_FILE_NOT_FOUND]

    def test_a_text_file_this_worker_cannot_read_is_quarantined_and_the_chunk_goes_on(
        self, inference: _Inference, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        inference.answers[SENTENCE] = [_entity(ADA, "PER")]
        reader = _Reader({"t1": "", "t2": SENTENCE}, uris={"t1": "texts/t1.txt"})

        def refuse(table_name: str, view: Any) -> Any:
            raise PermissionError(13, "Permission denied", view.uri)

        monkeypatch.setattr(reader, "open_media", refuse)

        _, outcome = _process(reader, ["t1", "t2"])

        assert ([item.reason for item in outcome.quarantined], outcome.produced) == ([TEXT_FILE_UNREADABLE], 1)

    def test_a_text_file_is_read_as_the_importer_reads_one(self, inference: _Inference) -> None:
        """Its line ends made line feeds: the offsets found on it hold on the content an import would give."""
        reader = _Reader(
            {"t1": ""}, uris={"t1": "texts/t1.txt"}, files={"texts/t1.txt": b"Ada Lovelace\r\nmet London."}
        )

        _process(reader, ["t1"])

        assert [call.text for call in inference.calls] == ["Ada Lovelace\nmet London."]

    def test_a_text_file_that_is_not_utf8_is_quarantined(self, inference: _Inference) -> None:
        reader = _Reader({"t1": ""}, uris={"t1": "texts/t1.txt"}, files={"texts/t1.txt": b"\xff\xfe\xfa"})

        _, outcome = _process(reader, ["t1"])

        assert [item.reason for item in outcome.quarantined] == [TEXT_NOT_UTF8]

    def test_a_missing_text_is_quarantined(self, inference: _Inference) -> None:
        _, outcome = _process(_Reader({}), ["t1"])

        assert [(item.item_id, item.reason) for item in outcome.quarantined] == [("t1", "media not found")]

    def test_a_text_the_server_refuses_costs_only_itself(self, inference: _Inference) -> None:
        inference.bad.add("refused")
        inference.answers[SENTENCE] = [_entity(ADA, "PER")]

        result, outcome = _process(_Reader({"t1": "refused", "t2": SENTENCE}), ["t1", "t2"])

        assert [text["view_id"] for text in result["texts"]] == ["t2"]
        assert [(item.item_id, item.reason, (item.detail or {}).get("record_id")) for item in outcome.quarantined] == [
            ("t1", "refused by the inference server", "rec-t1")
        ]

    def test_texts_all_refused_with_a_witness_accepted_are_the_texts_fault(self, inference: _Inference) -> None:
        inference.bad.update({"refused", "refused too"})

        result, outcome = _process(_Reader({"t1": "refused", "t2": "refused too"}), ["t1", "t2"])

        assert (result["texts"], [item.item_id for item in outcome.quarantined]) == ([], ["t1", "t2"])
        assert inference.calls[-1].text == WITNESS_TEXT

    def test_a_server_that_refuses_even_the_witness_text_is_at_fault(self, inference: _Inference) -> None:
        inference.status_for_everything = 500

        with pytest.raises(TransientError, match="witness text"):
            _process(_Reader({"t1": SENTENCE}), ["t1"])

    @pytest.mark.parametrize("status", [503, 429])
    def test_a_server_that_does_not_answer_makes_the_chunk_transient(self, inference: _Inference, status: int) -> None:
        inference.status_for_everything = status

        with pytest.raises(TransientError):
            _process(_Reader({"t1": SENTENCE}), ["t1"])

    def test_a_request_that_can_never_pass_fails_the_chunk(self, inference: _Inference) -> None:
        inference.status_for_everything = 404

        with pytest.raises(PixanoInferenceError):
            _process(_Reader({"t1": SENTENCE}), ["t1"])

    def test_the_client_is_closed_even_when_the_chunk_fails(self, inference: _Inference) -> None:
        inference.status_for_everything = 503

        with pytest.raises(TransientError):
            _process(_Reader({"t1": SENTENCE}), ["t1"])

        assert inference.opened == inference.closed == 1


class TestPlanning:
    def test_a_dataset_without_text_is_refused(self, inference: _Inference) -> None:
        with pytest.raises(ValueError, match="no text"):
            list(KIND.plan(_Reader({}, tables={"entities": Entity}), PARAMS))  # type: ignore[arg-type]

    def test_a_dataset_without_an_entity_table_is_refused(self, inference: _Inference) -> None:
        with pytest.raises(ValueError, match="'entities' table"):
            list(KIND.plan(_Reader({"t1": SENTENCE}, tables={"texts": Text}), PARAMS))  # type: ignore[arg-type]

    def test_entities_whose_category_is_not_text_are_refused_before_anything_runs(self, inference: _Inference) -> None:
        from pydantic import create_model

        Numbered = create_model("Numbered", __base__=Entity, category=(int, 0))

        with pytest.raises(ValueError, match="not text"):
            list(KIND.plan(_Reader({"t1": SENTENCE}, tables={"texts": Text, "entities": Numbered}), PARAMS))  # type: ignore[arg-type]

    def test_a_job_asking_for_another_media_type_is_refused_whole(self, inference: _Inference) -> None:
        params = KIND.validate_params({"model": "fake-ner", "media": ["image"]})

        with pytest.raises(ValueError, match="image"):
            list(KIND.plan(_Reader({"t1": SENTENCE}), params))  # type: ignore[arg-type]

    def test_a_model_the_server_does_not_serve_is_refused(self, inference: _Inference) -> None:
        with pytest.raises(ValueError, match="named 'spacy'"):
            list(KIND.plan(_Reader({"t1": SENTENCE}), KIND.validate_params({"model": "spacy"})))  # type: ignore[arg-type]

    def test_the_texts_are_cut_into_chunks(self, inference: _Inference) -> None:
        params = KIND.validate_params({"model": "fake-ner", "chunk_size": 2})

        chunks = list(KIND.plan(_Reader({f"t{index}": SENTENCE for index in range(5)}), params))  # type: ignore[arg-type]

        assert [chunk.payload["view_ids"] for chunk in chunks] == [["t0", "t1"], ["t2", "t3"], ["t4"]]


class TestAgainstRealLance:
    """What a recognition writes next to the spans already there."""

    @pytest.fixture
    def corpus(self, tmp_path):
        from pixano.datasets import Dataset
        from pixano.datasets.dataset_info import DatasetInfo
        from pixano.schemas import Record

        dataset = Dataset.create(
            tmp_path / "corpus",
            DatasetInfo(id="corpus", name="Corpus", record=Record, entity=Entity, views={"text": Text}),
        )
        dataset.add_records(
            {
                "records": [Record(id="r1")],
                "texts": [Text(id="t1", record_id="r1", logical_name="text", content=SENTENCE)],
            }
        )
        return dataset

    @staticmethod
    def _writer(corpus, job_id: str = "job-1", model: str = "fake-ner") -> JobWriter:
        return JobWriter(lambda: corpus, "ner", job_id, "model", params={"model": model}, model=ModelIdentity(model))

    def _recognize(
        self, corpus, found: list[tuple[tuple[int, int], str]], model: str = "fake-ner", **params: Any
    ) -> None:
        """A chunk of one text, `t1`, where the model recognized these mentions."""
        writer = self._writer(corpus, model=model)
        validated = KIND.validate_params({"model": model, **params})
        KIND.prepare(writer, validated)
        mentions = [
            {"text": SENTENCE[start:end], "label": label, "start": start, "end": end} for (start, end), label in found
        ]
        KIND.write(
            writer,
            {"texts": [{"view_id": "t1", "record_id": "r1", "mentions": mentions}], "skipped": 0, "quarantined": []},
            {},
            validated,  # type: ignore[arg-type]
        )

    @staticmethod
    def _person_marks(corpus, span_id: str, span: tuple[int, int], name: str, **fields: Any) -> None:
        """A span a person marked, with its object."""
        from pixano.schemas import TextSpan

        corpus.add_data("entities", [corpus.info.entity(id=f"e-{span_id}", record_id="r1", category=name)])
        start, end = span
        corpus.add_data(
            "text_spans",
            [
                TextSpan(
                    id=span_id,
                    record_id="r1",
                    view_id="t1",
                    entity_id=f"e-{span_id}",
                    mention=SENTENCE[start:end],
                    spans_start=[start],
                    spans_end=[end],
                    source_type="human",
                    **fields,
                )
            ],
        )

    @staticmethod
    def _spans(corpus) -> dict[str, tuple[str, str, str]]:
        """Each span's mention, class, and who wrote it."""
        classes = {entity.id: entity.category for entity in corpus.get_data("entities", limit=None)}
        return {
            span.id: (span.mention, classes.get(span.entity_id, ""), span.source_type)
            for span in corpus.get_data("text_spans", limit=None)
        }

    def test_gives_a_dataset_without_text_spans_their_table(self, corpus) -> None:
        assert "text_spans" not in corpus.info.tables

        self._recognize(corpus, [(ADA, "PER")])

        assert "text_spans" in corpus.info.tables

    def test_writes_each_mention_with_its_object_pending_review(self, corpus) -> None:
        self._recognize(corpus, [(ADA, "PER"), (LONDON, "LOC")])

        spans = corpus.get_data("text_spans", limit=None)
        assert sorted((span.mention, span.spans_start, span.spans_end) for span in spans) == [
            ("Ada Lovelace", [0], [12]),
            ("London", [36], [42]),
        ]
        assert {span.review_status for span in spans} == {"pending"}
        assert json.loads(spans[0].source_metadata)["model"] == "fake-ner"
        assert sorted(self._spans(corpus).values()) == [("Ada Lovelace", "PER", "model"), ("London", "LOC", "model")]

    def test_a_mention_over_a_persons_span_of_the_same_class_is_not_written(self, corpus) -> None:
        self._recognize(corpus, [])  # the class field and the table appear with the first job
        self._person_marks(corpus, "h1", (0, 3), "per")

        self._recognize(corpus, [(ADA, "PER")])

        assert self._spans(corpus) == {"h1": ("Ada", "per", "human")}

    def test_a_mention_over_a_persons_span_of_another_class_is_not_written_either(self, corpus) -> None:
        """The person corrected the class, or named the entity: the stretch of text is settled."""
        self._recognize(corpus, [])
        self._person_marks(corpus, "h1", ADA, "ORG")

        self._recognize(corpus, [(ADA, "PER")])

        assert self._spans(corpus) == {"h1": ("Ada Lovelace", "ORG", "human")}

    def test_a_model_span_a_person_accepted_by_editing_it_holds_back_the_next_run(self, corpus) -> None:
        self._recognize(corpus, [(LONDON, "LOC")])
        (span,) = corpus.get_data("text_spans", limit=None)
        span.review_status = "accepted"
        corpus.update_data("text_spans", [span])

        self._recognize(corpus, [(LONDON, "PER")])

        assert [(name, source) for _, name, source in self._spans(corpus).values()] == [("LOC", "model")]

    def test_a_mention_touching_a_persons_span_is_written(self, corpus) -> None:
        """Offsets leave their end out: London ends where the full stop starts."""
        self._recognize(corpus, [])
        self._person_marks(corpus, "h1", (42, 43), "")

        self._recognize(corpus, [(LONDON, "LOC")])

        assert len(self._spans(corpus)) == 2

    def test_an_empty_span_of_a_person_holds_nothing_back(self, corpus) -> None:
        self._recognize(corpus, [])
        self._person_marks(corpus, "h1", (38, 38), "LOC")

        self._recognize(corpus, [(LONDON, "LOC")])

        assert len(self._spans(corpus)) == 2

    def test_a_model_span_whose_object_a_person_worked_on_holds_back_its_place(self, corpus) -> None:
        """The object holds a person's work elsewhere — a child object here: the writer keeps it, so
        proposing the entity again would put a second span on the same words."""
        self._recognize(corpus, [(ADA, "PER")])
        (span,) = corpus.get_data("text_spans", limit=None)
        corpus.add_data("entities", [corpus.info.entity(id="child", record_id="r1", parent_id=span.entity_id)])

        self._recognize(corpus, [(ADA, "ORG")])

        assert [(name, source) for _, name, source in self._spans(corpus).values()] == [("PER", "model")]

    def test_a_persons_span_without_a_class_stands_for_every_class(self, corpus) -> None:
        self._recognize(corpus, [])
        self._person_marks(corpus, "h1", LONDON, "")

        self._recognize(corpus, [(LONDON, "LOC")])

        assert self._spans(corpus) == {"h1": ("London", "", "human")}

    def test_a_mention_beside_a_persons_span_is_written(self, corpus) -> None:
        self._recognize(corpus, [])
        self._person_marks(corpus, "h1", ADA, "PER")

        self._recognize(corpus, [(BABBAGE, "PER")])

        assert len(self._spans(corpus)) == 2

    def test_its_own_pending_spans_are_replaced_by_a_rerun(self, corpus) -> None:
        self._recognize(corpus, [(ADA, "PER"), (LONDON, "LOC")])

        self._recognize(corpus, [(ADA, "PER")])

        assert sorted(self._spans(corpus).values()) == [("Ada Lovelace", "PER", "model")]
        assert len(corpus.get_data("entities", limit=None)) == 1

    def test_another_models_spans_stay(self, corpus) -> None:
        self._recognize(corpus, [(ADA, "PER")], model="other-ner")

        self._recognize(corpus, [(LONDON, "LOC")])

        assert sorted(mention for mention, _, _ in self._spans(corpus).values()) == ["Ada Lovelace", "London"]

    def test_a_job_for_other_classes_keeps_the_spans_of_the_first(self, corpus) -> None:
        self._recognize(corpus, [(ADA, "PER")], entity_types=["PER"])

        self._recognize(corpus, [], entity_types=["LOC"])

        assert [name for _, name, _ in self._spans(corpus).values()] == ["PER"]

    def test_replacing_the_previous_spans_drops_every_models_pending_spans_but_what_a_person_accepted(
        self, corpus
    ) -> None:
        """Only planning reaches another model's spans: a write replaces its own model's alone."""
        self._recognize(corpus, [(ADA, "PER"), (LONDON, "LOC")], model="other-ner")
        first = next(span for span in corpus.get_data("text_spans", limit=None) if span.mention == "Ada Lovelace")
        first.review_status = "accepted"
        corpus.update_data("text_spans", [first])

        KIND.prepare(self._writer(corpus), KIND.validate_params({"model": "fake-ner", "replace_previous": True}))

        assert [span.id for span in corpus.get_data("text_spans", limit=None)] == [first.id]
        assert len(corpus.get_data("entities", limit=None)) == 1

    def test_replacing_the_previous_spans_of_some_classes_keeps_the_others(self, corpus) -> None:
        self._recognize(corpus, [(ADA, "PER"), (LONDON, "LOC")], model="other-ner")

        params = KIND.validate_params({"model": "fake-ner", "replace_previous": True, "entity_types": ["loc"]})
        KIND.prepare(self._writer(corpus), params)

        assert [name for _, name, _ in self._spans(corpus).values()] == ["PER"]

    def test_a_job_for_other_classes_writes_beside_the_spans_it_leaves_alone(self, corpus) -> None:
        self._recognize(corpus, [(ADA, "PER")], entity_types=["PER"])

        self._recognize(corpus, [(LONDON, "LOC")], entity_types=["LOC"])

        assert sorted((mention, name) for mention, name, _ in self._spans(corpus).values()) == [
            ("Ada Lovelace", "PER"),
            ("London", "LOC"),
        ]

    def test_a_worker_whose_dataset_predates_the_text_spans_table_still_writes(self, corpus, tmp_path) -> None:
        """Its cached dataset holds metadata without the table another worker's planning added. The
        entities have their class field already: adding it would reread the metadata, table included."""
        from pixano.datasets import Dataset

        self._writer(corpus).ensure_label_field()
        stale = Dataset(tmp_path / "corpus")
        KIND.prepare(self._writer(corpus), KIND.validate_params({"model": "fake-ner"}))
        assert "text_spans" not in stale.info.tables
        mention = {"text": "London", "label": "LOC", "start": LONDON[0], "end": LONDON[1]}

        KIND.write(
            self._writer(stale),
            {"texts": [{"view_id": "t1", "record_id": "r1", "mentions": [mention]}], "skipped": 0, "quarantined": []},
            {},
            KIND.validate_params({"model": "fake-ner"}),  # type: ignore[arg-type]
        )

        assert [span.mention for span in Dataset(tmp_path / "corpus").get_data("text_spans", limit=None)] == ["London"]
