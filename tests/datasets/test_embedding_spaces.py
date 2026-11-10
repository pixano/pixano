# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""A dataset's embedding spaces as `embeddings.json` describes them: one per model, and a default."""

from dataclasses import replace

import pytest

from pixano.datasets.embedding_spaces import (
    FIRST_TABLE,
    FORMAT_VERSION,
    TABLE_PREFIX,
    EmbeddingSpaces,
    is_embeddings_table,
    space_id,
)


CLIP = "clip"
CLIP_CHECKPOINT = "MobileCLIP2-S2"
SIGLIP = "siglip"


def _two_models() -> EmbeddingSpaces:
    spaces = EmbeddingSpaces()
    clip = spaces.new_space(CLIP, CLIP_CHECKPOINT, 512)
    spaces = spaces.with_space(clip)
    return spaces.with_space(spaces.new_space(SIGLIP, "so400m", 1152))


class TestTheDocument:
    def test_written_before_there_were_several_spaces_reads_as_one_space(self) -> None:
        legacy = {"table": "embeddings", "model_id": CLIP, "dim": 512, "metric": "cosine", "index_type": "IVF_SQ"}

        spaces = EmbeddingSpaces.from_document(legacy)

        (space,) = spaces.spaces
        assert (space.table, space.model_id, space.checkpoint, space.dim, space.index_type) == (
            "embeddings",
            CLIP,
            "",
            512,
            "IVF_SQ",
        )
        assert spaces.default == space.id == space_id(CLIP, "")

    def test_round_trips(self) -> None:
        spaces = _two_models()

        document = spaces.to_document()

        assert document["version"] == FORMAT_VERSION
        assert EmbeddingSpaces.from_document(document) == spaces

    def test_of_one_model_in_the_first_table_is_the_document_a_build_before_several_spaces_reads(self) -> None:
        clip = EmbeddingSpaces().new_space(CLIP, CLIP_CHECKPOINT, 512)
        spaces = EmbeddingSpaces().with_space(clip)

        document = spaces.to_document()

        assert document == clip.as_document()
        assert (document["table"], document["dim"], document["model_id"]) == (FIRST_TABLE, 512, CLIP)
        assert EmbeddingSpaces.from_document(document) == spaces

    def test_of_one_model_in_a_table_of_its_own_lists_it(self) -> None:
        spaces = _two_models()
        left = spaces.without(spaces.spaces[0].id)

        assert left.to_document()["spaces"] == [left.spaces[0].as_document()]

    def test_a_space_it_cannot_read_is_left_out_and_the_others_kept(self) -> None:
        document = _two_models().to_document()
        document["spaces"][0]["dim"] = 0

        spaces = EmbeddingSpaces.from_document(document)

        assert [space.model_id for space in spaces.spaces] == [SIGLIP]
        assert spaces.default == spaces.spaces[0].id
        assert not spaces.fully_read

    def test_a_space_written_twice_is_kept_once(self) -> None:
        document = _two_models().to_document()
        document["spaces"].append(dict(document["spaces"][0]))

        spaces = EmbeddingSpaces.from_document(document)

        assert (len(spaces.spaces), spaces.fully_read) == (2, False)

    def test_two_spaces_of_one_table_are_kept_once(self) -> None:
        document = _two_models().to_document()
        document["spaces"].append({**document["spaces"][0], "id": "clip-00000000"})

        spaces = EmbeddingSpaces.from_document(document)

        assert (len(spaces.spaces), spaces.fully_read) == (2, False)

    @pytest.mark.parametrize("table", ["records", "embeddings_another-space", ""])
    def test_a_space_naming_a_table_not_its_own_is_left_out(self, table: str) -> None:
        document = _two_models().to_document()
        document["spaces"][1]["table"] = table

        spaces = EmbeddingSpaces.from_document(document)

        assert ([space.model_id for space in spaces.spaces], spaces.fully_read) == ([CLIP], False)

    def test_the_document_of_one_space_is_that_of_the_first_table_whatever_it_says(self) -> None:
        spaces = EmbeddingSpaces.from_document({"table": "records", "model_id": CLIP, "dim": 512})

        assert spaces.spaces[0].table == FIRST_TABLE

    @pytest.mark.parametrize("dim", [float("inf"), "eight", None, -1, 2**31, 1e300])
    def test_a_space_of_no_dimension_is_left_out(self, dim: object) -> None:
        document = _two_models().to_document()
        document["spaces"][0]["dim"] = dim

        spaces = EmbeddingSpaces.from_document(document)

        assert ([space.model_id for space in spaces.spaces], spaces.fully_read) == ([SIGLIP], False)

    @pytest.mark.parametrize("version", [FORMAT_VERSION + 1, None, "2"])
    def test_a_version_it_does_not_know_is_read_but_not_fully(self, version: object) -> None:
        document = _two_models().to_document()
        document["version"] = version

        spaces = EmbeddingSpaces.from_document(document)

        assert (len(spaces.spaces), spaces.fully_read) == (2, False)

    def test_what_it_does_not_know_is_written_back_as_it_was(self) -> None:
        document = _two_models().to_document()
        document["written_by"] = "a later build"
        document["spaces"][1]["normalised"] = True

        rewritten = EmbeddingSpaces.from_document(document).to_document()

        assert rewritten == document

    @pytest.mark.parametrize("document", [[], "embeddings", None, {}, {"model_id": CLIP}])
    def test_neither_format_is_refused(self, document: object) -> None:
        with pytest.raises(ValueError):
            EmbeddingSpaces.from_document(document)


class TestFindingASpace:
    def test_by_its_id_by_its_models_name_and_the_default_when_none_is_named(self) -> None:
        spaces = _two_models()
        clip, siglip = spaces.spaces

        assert spaces.find(siglip.id) == siglip
        assert spaces.find(SIGLIP) == siglip
        assert spaces.find(None) == clip
        assert spaces.find("") == clip
        assert spaces.find("dinov2") is None

    def test_a_name_two_checkpoints_share_names_the_default_one_first(self) -> None:
        spaces = _two_models()
        other_clip = spaces.new_space(CLIP, "ViT-L-14", 768)
        spaces = spaces.with_space(other_clip).with_default(other_clip.id)

        assert spaces.find(CLIP) == other_clip

    def test_a_model_is_its_name_and_its_checkpoint(self) -> None:
        spaces = _two_models()
        clip = spaces.spaces[0]

        assert spaces.matching(CLIP, CLIP_CHECKPOINT) == clip
        assert spaces.matching(CLIP, "ViT-L-14") is None
        # A caller that cannot tell the checkpoint means the model of that name...
        assert spaces.matching(CLIP, "") == clip
        assert spaces.matching(CLIP, "", 512) == clip
        # ...unless its vectors' dimension says it is another.
        assert spaces.matching(CLIP, "", 768) is None

    def test_a_space_recorded_without_its_checkpoint_is_that_names_at_its_dimension(self) -> None:
        spaces = EmbeddingSpaces.from_document({"table": "embeddings", "model_id": CLIP, "dim": 512})

        assert spaces.matching(CLIP, CLIP_CHECKPOINT) == spaces.spaces[0]
        assert spaces.matching(CLIP, CLIP_CHECKPOINT, 512) == spaces.spaces[0]
        assert spaces.matching(CLIP, "ViT-L-14", 768) is None

    def test_the_very_model_matches_whatever_the_dimension(self) -> None:
        spaces = _two_models()

        assert spaces.matching(CLIP, CLIP_CHECKPOINT, 768) == spaces.spaces[0]

    def test_a_writer_finds_a_space_by_its_id_only(self) -> None:
        spaces = _two_models()
        clip = spaces.spaces[0]

        assert spaces.get(clip.id) == clip
        assert spaces.get(CLIP) is None


class TestChangingSpaces:
    def test_the_first_space_keeps_the_tables_old_name_and_the_others_get_their_own(self) -> None:
        spaces = _two_models()
        clip, siglip = spaces.spaces

        assert clip.table == FIRST_TABLE
        assert siglip.table == f"{TABLE_PREFIX}{siglip.id}"

    def test_the_first_space_is_the_default(self) -> None:
        spaces = _two_models()

        assert spaces.default == spaces.spaces[0].id

    def test_a_space_dropped_hands_the_default_to_the_first_left(self) -> None:
        spaces = _two_models()
        clip, siglip = spaces.spaces

        left = spaces.without(clip.id)

        assert (left.spaces, left.default) == ((siglip,), siglip.id)
        assert spaces.without(clip.id).without(siglip.id).default is None

    def test_another_space_can_be_made_the_default(self) -> None:
        spaces = _two_models()
        siglip = spaces.spaces[1]

        assert spaces.with_default(siglip.id).default == siglip.id
        with pytest.raises(KeyError):
            spaces.with_default("dinov2-00000000")

    def test_a_space_learning_its_checkpoint_keeps_its_id_and_table(self) -> None:
        spaces = EmbeddingSpaces.from_document({"table": "embeddings", "model_id": CLIP, "dim": 512})
        space = spaces.spaces[0]

        learnt = spaces.with_checkpoint(space, CLIP_CHECKPOINT).spaces[0]

        assert (learnt.id, learnt.table, learnt.checkpoint) == (space.id, space.table, CLIP_CHECKPOINT)

    def test_the_first_tables_name_is_free_again_once_its_space_is_gone(self) -> None:
        spaces = _two_models()
        left = spaces.without(spaces.spaces[0].id)

        assert left.new_space("dinov2", "vitb14", 768).table == FIRST_TABLE

    def test_a_new_space_never_takes_the_id_of_one_that_learnt_its_checkpoint(self) -> None:
        spaces = EmbeddingSpaces.from_document({"table": "embeddings", "model_id": CLIP, "dim": 512})
        learnt = spaces.with_checkpoint(spaces.spaces[0], CLIP_CHECKPOINT)

        new = learnt.new_space(CLIP, "", 512)

        assert new.id != learnt.spaces[0].id == space_id(CLIP, "")
        assert new.table == f"{TABLE_PREFIX}{new.id}"
        assert len(learnt.with_space(new).spaces) == 2

    def test_a_space_of_an_id_or_a_table_held_is_refused(self) -> None:
        spaces = _two_models()
        clip = spaces.spaces[0]

        with pytest.raises(ValueError):
            spaces.with_space(clip)
        with pytest.raises(ValueError):
            spaces.with_space(replace(clip, id="clip-00000000"))

    def test_a_default_naming_no_space_is_refused(self) -> None:
        clip = _two_models().spaces[0]

        with pytest.raises(ValueError):
            EmbeddingSpaces(spaces=(clip,), default="dinov2-00000000")
        with pytest.raises(ValueError):
            EmbeddingSpaces(spaces=(clip,), default=None)


def test_a_space_id_is_readable_and_tells_checkpoints_apart() -> None:
    assert space_id(CLIP, CLIP_CHECKPOINT).startswith("clip-")
    assert space_id(CLIP, CLIP_CHECKPOINT) != space_id(CLIP, "ViT-L-14")
    assert space_id("Open CLIP/ViT", "").startswith("open-clip-vit-")
    # Cut where the name had punctuation, the readable part ends with no dash of its own.
    assert "--" not in space_id("a" * 39 + "/vit", "")


@pytest.mark.parametrize(
    ("name", "holds_embeddings"),
    [("embeddings", True), ("embeddings_clip-3f2a9c1d", True), ("records", False), ("image_embeddings", False)],
)
def test_a_spaces_table_is_told_by_its_name(name: str, holds_embeddings: bool) -> None:
    assert is_embeddings_table(name) is holds_embeddings
