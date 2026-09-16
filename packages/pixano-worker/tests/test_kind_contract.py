# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""La suite que tout type de job doit passer.

Elle est paramétrée sur le registre, pas sur une liste écrite à la main : enregistrer un
nouveau type l'y soumet automatiquement, et c'est la seule façon qu'un contrat gelé le reste.
Un type qui échouerait ici casserait le moteur en production, pas seulement ses propres
résultats.

Les exemples de paramètres vivent dans `CONTRACT_EXAMPLES`. Un type sans exemple fait échouer
la suite délibérément : ajouter un type sans dire comment l'exercer reviendrait à le
soustraire au contrat.
"""

import hashlib
from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest
from pixano_worker.kinds import JobParams, default_registry
from pixano_worker.kinds.base import JobKind
from pixano_worker.media import MediaResolver
from pixano_worker.reader import JobReader
from pixano_worker.writer import JobWriter


#: Le vocabulaire de provenance des schémas Pixano. Écrire autre chose est refusé à l'écriture.
SOURCE_TYPES = {"model", "human", "ground_truth", "other"}

#: De quoi exercer chaque type : des paramètres valides, et une table où écrire.
CONTRACT_EXAMPLES: dict[str, dict[str, Any]] = {
    "fake": {"task_count": 40, "chunk_size": 10, "seconds_per_task": 0.0, "write_to": "toy"},
    # Le dataset du contrat est vide, donc la planification ne produit aucun chunk et rien
    # n'est appelé sur l'inference — ce qui est le but : le contrat éprouve la forme, pas le
    # modèle. Le chemin réel est vérifié de bout en bout dans la démonstration du lot.
    "embeddings": {"model": "clip", "chunk_size": 8},
    "label": {
        "record_ids": [f"rec-{n}" for n in range(25)],
        "label": "à-relire",
        "chunk_size": 10,
        "write_to": "toy",
    },
}

#: Les types qui savent ne rien écrire, et comment le leur demander.
QUIET_EXAMPLES: dict[str, dict[str, Any]] = {
    "fake": {**CONTRACT_EXAMPLES["fake"], "write_to": None},
    "label": {**CONTRACT_EXAMPLES["label"], "write_to": None},
}

REGISTRY = default_registry()


class _Target:
    """Une cible d'écriture qui se comporte comme LanceDB sur les trois opérations utilisées."""

    def __init__(self) -> None:
        self.rows: dict[str, Any] = {}
        self._embeddings_ready = False
        self.info = SimpleNamespace(tables={})

    def update_data(self, table_name: str, data: list[Any]) -> None:
        for row in data:
            self.rows[row.id] = row

    def delete_data(self, table_name: str, ids: list[str]) -> None:
        for row_id in ids:
            self.rows.pop(row_id, None)

    def get_data(self, table_name: str, ids: list[str]) -> list[Any]:
        return [self.rows[i] for i in ids if i in self.rows]

    def has_record_embeddings(self) -> bool:
        return self._embeddings_ready

    def create_record_embedding_table(self, dim: int, model_id: str) -> None:
        self._embeddings_ready = True
        self.info.tables["embeddings"] = _Vector

    def fingerprint(self) -> str:
        material = sorted(
            (row_id, getattr(row, "record_id", ""), repr(getattr(row, "labels", getattr(row, "vector", None))))
            for row_id, row in self.rows.items()
        )
        return hashlib.sha256(repr(material).encode()).hexdigest()


def _params(kind: JobKind) -> JobParams:
    if kind.name not in CONTRACT_EXAMPLES:
        pytest.fail(
            f"le type '{kind.name}' n'a pas d'exemple dans CONTRACT_EXAMPLES — "
            "un type sans exemple échappe au contrat"
        )
    return kind.validate_params(CONTRACT_EXAMPLES[kind.name])


#: Le dataset que voit le contrat. Non vide, parce qu'un type piloté par les données ne
#: produit rien sur un dataset vide — et que le contrat doit exercer ces types-là aussi.
CONTRACT_RECORDS = 25


class _Vector:
    """Une ligne d'embedding : pas de provenance, seulement un vecteur.

    Cette absence n'est pas un oubli du schéma Pixano — un embedding n'est pas une
    annotation, personne ne le relit, et le modèle qui l'a produit est décrit une fois pour
    toute la table.
    """

    def __init__(self, id: str, record_id: str, vector: Any) -> None:
        self.id, self.record_id, self.vector = id, record_id, vector


class _Row:
    def __init__(self, row_id: str, record_id: str = "", uri: str = "") -> None:
        self.id = row_id
        self.record_id = record_id
        self.uri = uri


class _Source:
    """Un dataset de vingt-cinq enregistrements, chacun avec une image désignée par chemin.

    Par chemin et non par octets, pour que le contrat n'ait pas à simuler des images : ce que
    le résolveur en fait est éprouvé ailleurs.
    """

    def count_rows_where(self, table_name: str, where: str | None = None) -> int:
        return CONTRACT_RECORDS

    def get_data(
        self,
        table_name: str,
        ids: list[str] | None = None,
        limit: int | None = None,
        skip: int = 0,
        where: str | None = None,
        record_ids: list[str] | None = None,
    ) -> list[Any]:
        if table_name == "images":
            return [_Row(f"img-{i}", record_id=i, uri=f"/medias/{i}.jpg") for i in record_ids or []]
        end = CONTRACT_RECORDS if limit is None else min(skip + limit, CONTRACT_RECORDS)
        return [_Row(f"rec-{n}") for n in range(skip, end)]

    def get_view_binary(self, table_name: str, row_id: str) -> tuple[bytes, str] | None:
        return None


def _reader() -> JobReader:
    return JobReader(lambda: _Source(), MediaResolver("/medias", "/medias"))


def _execute(kind: JobKind, target: _Target, job_id: str) -> None:
    params = _params(kind)
    for chunk in kind.plan(_reader(), params):
        writer = JobWriter(lambda: target, kind.name, job_id, kind.source_type)
        kind.write(writer, kind.process(_reader(), chunk.payload, params), chunk.payload, params)


#: Largeur des vecteurs que l'inference simulée renvoie.
FAKE_DIM = 8


@pytest.fixture(autouse=True)
def _offline_inference(monkeypatch: pytest.MonkeyPatch) -> None:
    """Répondre à la place de l'inference.

    Le contrat éprouve la forme d'un type, pas la qualité d'un modèle : il doit tourner sans
    serveur, en une seconde, sur la machine de n'importe qui. Ce que le vrai modèle produit
    est vérifié de bout en bout ailleurs.
    """

    class _Client:
        def __init__(self, *_args: Any, **_kwargs: Any) -> None:
            pass

        def embedding(self, request: Any, **_kwargs: Any) -> Any:
            count = len(request.image) if isinstance(request.image, list) else 1
            vectors = np.full((count, FAKE_DIM), 0.1, dtype=np.float32)
            return SimpleNamespace(data=SimpleNamespace(embeddings=SimpleNamespace(to_numpy=lambda: vectors)))

    monkeypatch.setattr("pixano_worker.kinds.embeddings.SyncPixanoInferenceClient", _Client)


@pytest.fixture(params=REGISTRY.names())
def kind(request: pytest.FixtureRequest) -> JobKind:
    """Chaque type enregistré, à son tour."""
    registered = REGISTRY.get(request.param)
    assert registered is not None
    return registered


class TestDeclaration:
    def test_it_has_a_name(self, kind: JobKind) -> None:
        assert kind.name

    def test_its_parameters_forbid_unknown_fields(self, kind: JobKind) -> None:
        """C'est ce qui permet à l'application de refuser une faute de frappe à la soumission.

        Sans cette propriété, un paramètre mal orthographié passe la validation et se fait
        ignorer en silence : l'utilisateur obtient un job qui tourne avec d'autres réglages
        que ceux qu'il croit avoir posés.
        """
        assert kind.params_schema()["additionalProperties"] is False

    def test_it_declares_a_provenance_the_schemas_accept(self, kind: JobKind) -> None:
        """Un type qui déclarerait autre chose verrait ses écritures refusées à l'exécution."""
        assert kind.source_type in SOURCE_TYPES

    def test_its_parameter_example_is_valid(self, kind: JobKind) -> None:
        assert isinstance(_params(kind), JobParams)


class TestPlanning:
    def test_it_produces_work(self, kind: JobKind) -> None:
        assert list(kind.plan(_reader(), _params(kind)))

    def test_every_chunk_carries_at_least_one_task(self, kind: JobKind) -> None:
        """Un chunk vide bloquerait la progression : il consommerait un tour sans avancer."""
        assert all(chunk.task_count > 0 for chunk in kind.plan(_reader(), _params(kind)))

    def test_planning_twice_gives_the_same_work(self, kind: JobKind) -> None:
        """La planification doit être reproductible : un job replanifié après une coupure
        ne doit pas décrire un travail différent de celui déjà en partie exécuté."""
        first = [(c.payload, c.task_count) for c in kind.plan(_reader(), _params(kind))]
        second = [(c.payload, c.task_count) for c in kind.plan(_reader(), _params(kind))]

        assert first == second

    def test_the_payload_is_an_object(self, kind: JobKind) -> None:
        """Le schéma contraint les payloads à des objets ; un scalaire serait refusé en base."""
        assert all(isinstance(chunk.payload, dict) for chunk in kind.plan(_reader(), _params(kind)))


class TestExecution:
    def test_it_processes_every_chunk(self, kind: JobKind) -> None:
        params = _params(kind)

        for chunk in kind.plan(_reader(), params):
            kind.process(_reader(), chunk.payload, params)

    def test_its_outcome_accounts_for_every_task(self, kind: JobKind) -> None:
        """Le moteur refuse un bilan qui ne tombe pas juste ; mieux vaut l'apprendre ici qu'en production."""
        params = _params(kind)

        for chunk in kind.plan(_reader(), params):
            result = kind.process(_reader(), chunk.payload, params)
            assert kind.outcome(result, chunk.payload, chunk.task_count).total == chunk.task_count

    def test_writing_twice_changes_nothing(self, kind: JobKind) -> None:
        """L'idempotence, exigée de tous : les résultats vont dans LanceDB et l'avancement
        dans PostgreSQL, donc un worker qui meurt entre les deux refait le chunk."""
        target = _Target()
        _execute(kind, target, "job-1")
        first = (len(target.rows), target.fingerprint())

        _execute(kind, target, "job-1")

        assert (len(target.rows), target.fingerprint()) == first

    def test_a_resubmission_does_not_duplicate(self, kind: JobKind) -> None:
        target = _Target()
        _execute(kind, target, "job-1")
        first = (len(target.rows), target.fingerprint())

        _execute(kind, target, "job-2")

        assert (len(target.rows), target.fingerprint()) == first

    def test_every_annotation_says_where_it_came_from(self, kind: JobKind) -> None:
        """La provenance est exigée des annotations, pas de toute sortie.

        Un embedding n'en porte pas, et c'est cohérent : personne ne le relit, et le modèle
        qui l'a produit est décrit une fois pour toute la table plutôt que sur chaque ligne.
        Le contrat vérifie donc que ce qui *peut* porter une provenance en porte une juste.
        """
        target = _Target()

        _execute(kind, target, "job-1")

        assert target.rows, "un type qui écrit doit écrire quelque chose avec cet exemple"
        for row in target.rows.values():
            if not hasattr(row, "source_name"):
                continue
            assert row.source_name == kind.name
            assert row.source_type == kind.source_type

    def test_a_kind_can_be_told_to_write_nothing(self, kind: JobKind) -> None:
        """Certains types savent se taire — une statistique, un essai à blanc. Ceux qui ne le
        savent pas sont ignorés ici : c'est une capacité, pas une obligation du contrat."""
        if kind.name not in QUIET_EXAMPLES:
            pytest.skip(f"'{kind.name}' n'a pas de mode silencieux")
        params = kind.validate_params(QUIET_EXAMPLES[kind.name])
        target = _Target()

        for chunk in kind.plan(_reader(), params):
            writer = JobWriter(lambda: target, kind.name, "job-1", kind.source_type)
            kind.write(writer, kind.process(_reader(), chunk.payload, params), chunk.payload, params)

        assert target.rows == {}


class TestRegistry:
    def test_every_registered_kind_is_covered(self) -> None:
        """Le garde-fou du contrat : un type ajouté sans exemple fait échouer la suite."""
        assert set(REGISTRY.names()) <= set(CONTRACT_EXAMPLES)

    def test_two_kinds_cannot_share_a_name(self) -> None:
        from pixano_worker.kinds import FakeKind, Registry

        registry = Registry()
        registry.register(FakeKind())

        with pytest.raises(ValueError, match="déjà enregistré"):
            registry.register(FakeKind())
