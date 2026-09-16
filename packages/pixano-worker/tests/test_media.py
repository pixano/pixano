# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Tests du résolveur de médias."""

from typing import Any

import pytest
from pixano_worker.media import MediaResolver


class _View:
    def __init__(self, uri: str = "", view_id: str = "v1") -> None:
        self.uri = uri
        self.id = view_id


class _Source:
    """Un dataset qui sait rendre les octets d'une vue embarquée."""

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
    """Les deux racines diffèrent, comme dès que worker et inference sont sur deux machines."""
    return MediaResolver(media_root="/medias", inference_media_root="/data/media")


class TestTranslate:
    def test_moves_a_path_from_one_root_to_the_other(self, resolver: MediaResolver) -> None:
        assert resolver.translate("/medias/voc/000001.jpg") == "/data/media/voc/000001.jpg"

    def test_keeps_the_path_below_the_root(self, resolver: MediaResolver) -> None:
        assert resolver.translate("/medias/a/b/c.png") == "/data/media/a/b/c.png"

    def test_refuses_a_path_outside_the_declared_root(self, resolver: MediaResolver) -> None:
        """L'inference refuserait ce chemin ; autant le savoir ici et prendre l'autre route."""
        assert resolver.translate("/ailleurs/000001.jpg") is None

    def test_refuses_a_relative_path(self, resolver: MediaResolver) -> None:
        assert resolver.translate("voc/000001.jpg") is None

    def test_identical_roots_are_the_local_case(self) -> None:
        same = MediaResolver("/medias", "/medias")

        assert same.translate("/medias/a.jpg") == "/medias/a.jpg"


class TestResolve:
    def test_a_remote_url_passes_through(self, resolver: MediaResolver) -> None:
        """L'inference sait les lire elle-même : rien n'a à transiter par ici."""
        resolved = resolver.resolve(_Source(), "images", _View(uri="https://exemple/img.jpg"))

        assert resolved is not None
        assert resolved.value == "https://exemple/img.jpg"
        assert resolved.carried_bytes is False

    def test_an_s3_uri_passes_through(self, resolver: MediaResolver) -> None:
        resolved = resolver.resolve(_Source(), "images", _View(uri="s3://seau/img.jpg"))

        assert resolved is not None and resolved.carried_bytes is False

    def test_a_path_under_the_root_is_translated(self, resolver: MediaResolver) -> None:
        resolved = resolver.resolve(_Source(), "images", _View(uri="/medias/voc/1.jpg"))

        assert resolved is not None
        assert resolved.value == "/data/media/voc/1.jpg"
        assert resolved.carried_bytes is False

    def test_a_path_is_preferred_over_the_bytes(self, resolver: MediaResolver) -> None:
        """La préférence qui fait tout l'intérêt : rien ne doit être lu si un chemin suffit."""
        source = _Source({"v1": JPEG})

        resolver.resolve(source, "images", _View(uri="/medias/voc/1.jpg"))

        assert source.asked == [], "les octets ont été lus alors qu'un chemin existait"

    def test_embedded_media_are_sent_as_bytes(self, resolver: MediaResolver) -> None:
        """La route des datasets en mode embed — ceux qui existent aujourd'hui.

        Sans elle, un dataset dont les images vivent dans LanceDB ne serait pas traitable du
        tout, et le calcul d'embeddings qui fonctionne déjà cesserait de fonctionner.
        """
        resolved = resolver.resolve(_Source({"v1": JPEG}), "images", _View())

        assert resolved is not None
        assert resolved.value.startswith("data:image/jpeg;base64,")
        assert resolved.carried_bytes is True

    def test_a_path_outside_the_root_falls_back_to_bytes(self, resolver: MediaResolver) -> None:
        """L'inference refuserait ce chemin ; les octets sont la seule route restante."""
        resolved = resolver.resolve(_Source({"v1": JPEG}), "images", _View(uri="/ailleurs/1.jpg"))

        assert resolved is not None
        assert resolved.carried_bytes is True
        assert "hors racine" in resolved.reason

    def test_a_media_that_is_nowhere_resolves_to_nothing(self, resolver: MediaResolver) -> None:
        """Ni chemin ni octets : le type de job doit pouvoir sauter cet item plutôt que
        d'envoyer une référence vide à l'inference."""
        assert resolver.resolve(_Source(), "images", _View()) is None

    def test_it_says_which_route_it_took(self, resolver: MediaResolver) -> None:
        """Le coût qu'on cherche à éviter doit être comptable, pas découvert sur un gros
        dataset."""
        chemin = resolver.resolve(_Source(), "images", _View(uri="/medias/1.jpg"))
        octets = resolver.resolve(_Source({"v1": JPEG}), "images", _View())

        assert chemin is not None and octets is not None
        assert [chemin.carried_bytes, octets.carried_bytes] == [False, True]
        assert chemin.reason and octets.reason
