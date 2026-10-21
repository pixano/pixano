# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Tests of the media resolver."""

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from pixano_worker.media import MediaResolver


class _View:
    def __init__(self, uri: str = "", view_id: str = "v1") -> None:
        self.uri = uri
        self.id = view_id


class _Source:
    """A dataset that can return the bytes of an embedded view."""

    def __init__(self, blobs: dict[str, bytes] | None = None) -> None:
        self.blobs = blobs or {}
        self.asked: list[str] = []

    def get_view_binary(self, table_name: str, row_id: str) -> tuple[bytes, str] | None:
        self.asked.append(row_id)
        blob = self.blobs.get(row_id)
        return (blob, "image/jpeg") if blob else None


JPEG = b"\xff\xd8\xff" + b"0" * 64


@pytest.fixture
def resolver() -> MediaResolver:
    """The two roots differ, as they do as soon as worker and inference are on two machines."""
    return MediaResolver(media_root="/medias", inference_media_root="/data/media")


class TestTranslate:
    def test_moves_a_path_from_one_root_to_the_other(self, resolver: MediaResolver) -> None:
        assert resolver.translate("/medias/voc/000001.jpg") == "/data/media/voc/000001.jpg"

    def test_keeps_the_path_below_the_root(self, resolver: MediaResolver) -> None:
        assert resolver.translate("/medias/a/b/c.png") == "/data/media/a/b/c.png"

    def test_refuses_a_path_outside_the_declared_root(self, resolver: MediaResolver) -> None:
        """The inference would refuse this path; better to know it here and take the other route."""
        assert resolver.translate("/elsewhere/000001.jpg") is None

    @pytest.mark.parametrize(
        "escaping",
        ["/medias/../etc/passwd", "/medias/voc/../../etc/passwd", "/medias/./../elsewhere/a.jpg"],
    )
    def test_refuses_a_path_that_climbs_out_of_the_root(self, resolver: MediaResolver, escaping: str) -> None:
        """The lexical comparison let `..` through."""
        assert resolver.translate(escaping) is None

    def test_a_path_that_climbs_back_into_the_root_is_normalised(self, resolver: MediaResolver) -> None:
        assert resolver.translate("/medias/voc/../coco/a.jpg") == "/data/media/coco/a.jpg"

    def test_refuses_a_relative_path(self, resolver: MediaResolver) -> None:
        assert resolver.translate("voc/000001.jpg") is None

    def test_identical_roots_are_the_local_case(self) -> None:
        same = MediaResolver("/medias", "/medias")

        assert same.translate("/medias/a.jpg") == "/medias/a.jpg"


class TestResolve:
    def test_a_remote_url_passes_through(self, resolver: MediaResolver) -> None:
        """The inference can read them itself: nothing has to transit through here."""
        resolved = resolver.resolve(_Source(), "images", _View(uri="https://example.com/img.jpg"))

        assert resolved is not None
        assert resolved.value == "https://example.com/img.jpg"
        assert resolved.carried_bytes is False

    def test_an_s3_uri_passes_through(self, resolver: MediaResolver) -> None:
        resolved = resolver.resolve(_Source(), "images", _View(uri="s3://bucket/img.jpg"))

        assert resolved is not None and resolved.carried_bytes is False

    def test_a_path_under_the_root_is_translated(self, resolver: MediaResolver) -> None:
        resolved = resolver.resolve(_Source(), "images", _View(uri="/medias/voc/1.jpg"))

        assert resolved is not None
        assert resolved.value == "/data/media/voc/1.jpg"
        assert resolved.carried_bytes is False

    def test_a_path_is_preferred_over_the_bytes(self, resolver: MediaResolver) -> None:
        """The preference that is the whole point: nothing must be read if a path is enough."""
        source = _Source({"v1": JPEG})

        resolver.resolve(source, "images", _View(uri="/medias/voc/1.jpg"))

        assert source.asked == [], "the bytes were read although a path existed"

    def test_embedded_media_are_sent_as_bytes(self, resolver: MediaResolver) -> None:
        """The route of datasets in embed mode — the ones that exist today.

        Without it, a dataset whose images live in LanceDB could not be processed at all, and
        the embeddings computation that already works would stop working.
        """
        resolved = resolver.resolve(_Source({"v1": JPEG}), "images", _View())

        assert resolved is not None
        assert resolved.value.startswith("data:image/jpeg;base64,")
        assert resolved.carried_bytes is True

    def test_a_path_outside_the_root_falls_back_to_bytes(self, resolver: MediaResolver) -> None:
        """The inference would refuse this path; the bytes are the only route left."""
        resolved = resolver.resolve(_Source({"v1": JPEG}), "images", _View(uri="/elsewhere/1.jpg"))

        assert resolved is not None
        assert resolved.carried_bytes is True
        assert "outside the root" in resolved.reason

    def test_a_media_that_is_nowhere_resolves_to_nothing(self, resolver: MediaResolver) -> None:
        """Neither path nor bytes: the job kind must be able to skip this item rather than
        send an empty reference to the inference."""
        assert resolver.resolve(_Source(), "images", _View()) is None

    def test_it_says_which_route_it_took(self, resolver: MediaResolver) -> None:
        """The cost we are trying to avoid must be countable, not discovered on a large
        dataset."""
        by_path = resolver.resolve(_Source(), "images", _View(uri="/medias/1.jpg"))
        by_bytes = resolver.resolve(_Source({"v1": JPEG}), "images", _View())

        assert by_path is not None and by_bytes is not None
        assert [by_path.carried_bytes, by_bytes.carried_bytes] == [False, True]
        assert by_path.reason and by_bytes.reason

    @pytest.mark.parametrize(
        ("uri", "designation"),
        [
            ("https://example.com/img.jpg", "url"),
            ("s3://bucket/img.jpg", "url"),
            ("/medias/voc/1.jpg", "path"),
            ("", "bytes"),
        ],
    )
    def test_it_says_how_it_designates_each_medium(self, resolver: MediaResolver, uri: str, designation: str) -> None:
        """A URL was counted with the paths, as everything not sent
        as bytes was, although resending bytes cannot diagnose it.

        The bytes exist for the view without a URI only: a view carries one or the other.
        """
        resolved = resolver.resolve(_Source({"v1": JPEG} if not uri else {}), "images", _View(uri=uri))

        assert resolved is not None and resolved.designation == designation

    def test_what_to_check_for_refused_paths_names_the_inferences_root(self, resolver: MediaResolver) -> None:
        """The inference's side of the mount, not the worker's: the path it was sent is under it."""
        assert "under /data/media — check PIXANO_INFERENCE_MEDIA_ROOT" in resolver.path_refusal_diagnostic()


class TestUnconfigured:
    def test_refuses_to_resolve_and_says_which_variables_are_missing(self) -> None:
        """The former fallback sent `/medias` paths that only the compose stack can read."""
        resolver = MediaResolver.unconfigured()

        with pytest.raises(RuntimeError, match="PIXANO_MEDIA_ROOT"):
            resolver.resolve(_Source(), "images", _View(uri="/anywhere/a.jpg"))


class TestLocalPath:
    """The file a view names, for what the worker reads itself — a medium it resends as bytes."""

    RESOLVER = MediaResolver("/medias", "/srv/inference/medias")

    def test_an_absolute_path_under_the_root(self) -> None:
        assert self.RESOLVER.local_path(SimpleNamespace(uri="/medias/voc/a.jpg")) == "/medias/voc/a.jpg"

    def test_a_relative_reference_is_taken_from_the_root(self) -> None:
        assert self.RESOLVER.local_path(SimpleNamespace(uri="voc/a.jpg")) == "/medias/voc/a.jpg"

    @pytest.mark.parametrize("uri", ["/medias/../etc/passwd", "../etc/passwd", "/etc/passwd"])
    def test_nothing_outside_the_root(self, uri: str) -> None:
        assert self.RESOLVER.local_path(SimpleNamespace(uri=uri)) is None

    @pytest.mark.parametrize("uri", ["https://host/a.jpg", "s3://bucket/a.jpg", ""])
    def test_nothing_the_worker_does_not_hold(self, uri: str) -> None:
        assert self.RESOLVER.local_path(SimpleNamespace(uri=uri)) is None

    def test_nothing_a_link_under_the_root_leads_to_outside_it(self, tmp_path: Path) -> None:
        """The check was on the path's text, and opening the file follows links: a link under the
        root to a file outside it was read, and resent to the inference, as a medium."""
        root, outside = tmp_path / "media", tmp_path / "outside"
        root.mkdir()
        outside.mkdir()
        (outside / "a.jpg").write_bytes(JPEG)
        (root / "a.jpg").symlink_to(outside / "a.jpg")

        assert MediaResolver(str(root), "/srv/inference/medias").local_path(SimpleNamespace(uri="a.jpg")) is None

    def test_links_that_stay_under_the_root_are_followed(self, tmp_path: Path) -> None:
        """A root mounted through a link, and a link from one folder of the root to another."""
        storage = tmp_path / "storage"
        (storage / "voc").mkdir(parents=True)
        (storage / "voc" / "a.jpg").write_bytes(JPEG)
        (storage / "a.jpg").symlink_to(storage / "voc" / "a.jpg")
        root = tmp_path / "media"
        root.symlink_to(storage)

        resolver = MediaResolver(str(root), "/srv/inference/medias")

        assert resolver.local_path(SimpleNamespace(uri="a.jpg")) == str(root / "a.jpg")
