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
        provenance = JobWriter(lambda: dataset, "fake", "job-42", "other").provenance()

        assert provenance["source_type"] == "other"
        assert provenance["source_name"] == "fake"
        assert json.loads(provenance["source_metadata"])["job_id"] == "job-42"


class TestAgainstRealLance:
    """Les tests précédents passent par un double ; ceux-ci écrivent dans un vrai LanceDB.

    Le double reproduit les deux opérations dont l'écrivain se sert, mais pas les contrôles
    d'intégrité de Pixano — et ce sont eux qui ont révélé qu'une sortie de job ne peut pas
    inventer les enregistrements auxquels elle se rattache.
    """

    @pytest.fixture
    def toy(self, tmp_path):
        from pixano.datasets import Dataset
        from pixano.datasets.dataset_info import DatasetInfo
        from pixano.schemas.annotations.classification import Classification
        from pixano.schemas.records import Record

        dataset = Dataset.create(
            tmp_path / "jouet",
            DatasetInfo(id="jouet", name="Jouet", record=Record, classification=Classification),
        )
        dataset.add_data("records", [Record(id=f"task-{n}") for n in range(60)])
        return dataset

    @staticmethod
    def _run(toy, job_id: str, task_count: int) -> None:
        from pixano_worker.kinds import FakeKind, FakeParams

        kind = FakeKind()
        params = FakeParams(task_count=task_count, chunk_size=20, seconds_per_task=0.0, write_to="classifications")
        for chunk in kind.plan("jouet", params):
            writer = JobWriter(lambda: toy, kind.name, job_id, kind.source_type)
            kind.write(writer, kind.process(chunk.payload, params), chunk.payload, params)

    @staticmethod
    def _fingerprint(toy) -> tuple[int, str]:
        rows = toy.get_data("classifications", limit=10_000)
        material = sorted((r.id, r.record_id, tuple(r.labels), r.source_name) for r in rows)
        return len(rows), hashlib.sha256(repr(material).encode()).hexdigest()

    def test_the_same_job_run_twice_writes_the_same_content(self, toy) -> None:
        """La définition de fini du lot, contre le vrai magasin."""
        self._run(toy, "job-1", 60)
        first = self._fingerprint(toy)

        self._run(toy, "job-1", 60)

        assert self._fingerprint(toy) == first

    def test_resubmitting_does_not_duplicate(self, toy) -> None:
        self._run(toy, "job-1", 60)
        first = self._fingerprint(toy)

        self._run(toy, "job-2", 60)

        assert self._fingerprint(toy) == first

    def test_every_row_says_where_it_came_from(self, toy) -> None:
        self._run(toy, "job-1", 20)

        rows = toy.get_data("classifications", limit=100)
        assert rows
        for row in rows:
            assert row.source_name == "fake"
            assert json.loads(row.source_metadata)["job_id"] == "job-1"

    def test_a_kind_that_runs_no_model_does_not_claim_to(self, toy) -> None:
        """`model` désignerait une prédiction ; celle-ci n'en est pas une."""
        self._run(toy, "job-1", 20)

        assert toy.get_data("classifications", limit=1)[0].source_type == "other"

    def test_it_cannot_write_into_a_dataset_it_was_not_built_for(self, toy, tmp_path) -> None:
        """Le garde-fou est structurel, et vaut mieux qu'une convention de nommage.

        Les noms de tables sont canoniques dans Pixano, donc « une table de jouet » n'existe
        pas. Mais un dataset réel n'a pas les enregistrements que ce type invente, et le
        contrôle d'intégrité refuse la sortie plutôt que de la laisser s'installer.
        """
        from pixano.datasets import Dataset
        from pixano.datasets.dataset_info import DatasetInfo
        from pixano.schemas.annotations.classification import Classification
        from pixano.schemas.records import Record

        autre = Dataset.create(
            tmp_path / "autre",
            DatasetInfo(id="autre", name="Autre", record=Record, classification=Classification),
        )
        autre.add_data("records", [Record(id="une-vraie-image")])

        with pytest.raises(Exception):
            self._run(autre, "job-1", 20)

    def test_a_kind_declares_what_it_produces(self, dataset: _FakeDataset) -> None:
        """Le vocabulaire est celui des schémas : model, human, ground_truth, other.

        Écrire « job » y serait refusé, et c'est tant mieux — ce qui compte pour un relecteur
        est de savoir si une annotation vient d'un modèle, pas quel rouage l'a écrite.
        """
        assert JobWriter(lambda: dataset, "embeddings", "j", "model").provenance()["source_type"] == "model"
