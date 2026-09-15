# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Tests de l'écriture idempotente des résultats de jobs."""

import hashlib
import json
from typing import Any

import pytest
from pixano_worker.writer import JobWriter, derive_id


class _FakeRow:
    """Une ligne quelconque, avec l'identifiant que l'écrivain lui pose."""

    def __init__(self, payload: str) -> None:
        self.id = ""
        self.payload = payload


class _FakeDataset:
    """Un dataset en mémoire, qui se comporte comme LanceDB sur les deux seules opérations
    dont l'écrivain se sert : l'upsert par identifiant et la suppression par identifiants."""

    def __init__(self) -> None:
        self.tables: dict[str, dict[str, Any]] = {}

    def update_data(self, table_name: str, data: list[Any]) -> None:
        table = self.tables.setdefault(table_name, {})
        for row in data:
            table[row.id] = row

    def delete_data(self, table_name: str, ids: list[str]) -> None:
        table = self.tables.setdefault(table_name, {})
        for row_id in ids:
            table.pop(row_id, None)

    def get_data(self, table_name: str, ids: list[str]) -> list[Any]:
        table = self.tables.get(table_name, {})
        return [table[row_id] for row_id in ids if row_id in table]

    def checksum(self, table_name: str) -> str:
        """Une empreinte du contenu, insensible à l'ordre d'écriture."""
        table = self.tables.get(table_name, {})
        material = json.dumps(sorted((row_id, row.payload) for row_id, row in table.items()))
        return hashlib.sha256(material.encode()).hexdigest()


@pytest.fixture
def dataset() -> _FakeDataset:
    return _FakeDataset()


def _writer(dataset: _FakeDataset, job_id: str = "job-1") -> JobWriter:
    return JobWriter(lambda: dataset, kind="fake", job_id=job_id)


class TestDeriveId:
    """L'identité vient du travail, pas de l'exécution qui l'a produit."""

    def test_is_stable_across_calls(self) -> None:
        assert derive_id("fake", "item-1", 0) == derive_id("fake", "item-1", 0)

    def test_separates_outputs_of_one_key(self) -> None:
        assert derive_id("fake", "item-1", 0) != derive_id("fake", "item-1", 1)

    def test_separates_keys(self) -> None:
        assert derive_id("fake", "item-1", 0) != derive_id("fake", "item-2", 0)

    def test_separates_kinds(self) -> None:
        """Deux traitements sur le même item ne doivent pas s'écraser l'un l'autre."""
        assert derive_id("fake", "item-1", 0) != derive_id("embeddings", "item-1", 0)

    def test_does_not_depend_on_the_job(self) -> None:
        """La propriété centrale du lot : resoumettre remplace au lieu de dupliquer.

        Un identifiant qui porterait le job produirait des lignes neuves à chaque
        soumission, et le même traitement relancé doublerait le contenu du dataset.
        """
        first = _writer(_FakeDataset(), job_id="job-1").ids_for("item-1", 3)
        second = _writer(_FakeDataset(), job_id="job-2").ids_for("item-1", 3)

        assert first == second


class TestReplay:
    """« Le même job lancé deux fois » — la définition de fini du lot."""

    def test_a_second_run_changes_nothing(self, dataset: _FakeDataset) -> None:
        rows = lambda: [_FakeRow("a"), _FakeRow("b"), _FakeRow("c")]  # noqa: E731

        _writer(dataset).replace("toy", "item-1", rows())
        first = (len(dataset.tables["toy"]), dataset.checksum("toy"))
        _writer(dataset).replace("toy", "item-1", rows())

        assert (len(dataset.tables["toy"]), dataset.checksum("toy")) == first

    def test_a_different_job_does_not_duplicate(self, dataset: _FakeDataset) -> None:
        """Une resoumission est un job différent, et ne doit pas doubler le contenu."""
        _writer(dataset, "job-1").replace("toy", "item-1", [_FakeRow("a"), _FakeRow("b")])
        before = dataset.checksum("toy")

        _writer(dataset, "job-2").replace("toy", "item-1", [_FakeRow("a"), _FakeRow("b")])

        assert len(dataset.tables["toy"]) == 2
        assert dataset.checksum("toy") == before

    def test_a_changed_result_replaces_the_old_one(self, dataset: _FakeDataset) -> None:
        _writer(dataset).replace("toy", "item-1", [_FakeRow("avant")])

        _writer(dataset).replace("toy", "item-1", [_FakeRow("après")])

        assert [row.payload for row in dataset.tables["toy"].values()] == ["après"]

    def test_a_shorter_result_leaves_nothing_behind(self, dataset: _FakeDataset) -> None:
        """Le cas que le simple remplacement ne couvre pas.

        Un modèle qui détectait cinq objets et n'en voit plus que deux laisserait trois
        lignes orphelines que rien ne viendrait jamais nettoyer.
        """
        _writer(dataset).replace("toy", "item-1", [_FakeRow(str(n)) for n in range(5)])

        _writer(dataset).replace("toy", "item-1", [_FakeRow("0"), _FakeRow("1")])

        assert len(dataset.tables["toy"]) == 2

    def test_an_empty_result_clears_the_key(self, dataset: _FakeDataset) -> None:
        _writer(dataset).replace("toy", "item-1", [_FakeRow("a"), _FakeRow("b")])

        _writer(dataset).replace("toy", "item-1", [])

        assert dataset.tables["toy"] == {}

    def test_other_keys_are_untouched(self, dataset: _FakeDataset) -> None:
        """Le nettoyage est cadré à la clé : effacer les sorties d'un item ne doit pas
        toucher à celles d'un autre, ni à celles d'un autre chunk du même job."""
        _writer(dataset).replace("toy", "item-1", [_FakeRow("a"), _FakeRow("b")])
        _writer(dataset).replace("toy", "item-2", [_FakeRow("c")])

        _writer(dataset).replace("toy", "item-1", [])

        assert [row.payload for row in dataset.tables["toy"].values()] == ["c"]


class TestProvenance:
    """Aucune sortie de job ne doit atterrir dans un dataset sans qu'on sache d'où elle vient."""

    def test_names_the_kind_and_the_job(self, dataset: _FakeDataset) -> None:
        provenance = _writer(dataset, "job-42").provenance()

        assert provenance["source_type"] == "job"
        assert provenance["source_name"] == "fake"
        assert json.loads(provenance["source_metadata"])["job_id"] == "job-42"
