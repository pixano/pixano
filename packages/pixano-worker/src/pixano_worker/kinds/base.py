# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Les trois contrats qui font un type de job.

Un type de job est un greffon : il apporte ses paramètres, sait découper son travail, sait
traiter un lot et sait écrire ce qu'il a produit. Le moteur — réclamation, bail, reprise,
progression, annulation — ne connaît rien de son contenu.

Les trois contrats :

- **`Params`**, un modèle pydantic. Son schéma JSON est publié en base pour que l'application
  refuse des paramètres invalides à la soumission, plutôt que de mettre en file un job qui
  échouerait à l'exécution.
- **`plan`**, qui découpe le travail en chunks. Il s'exécute dans le worker, pas dans
  l'application : découper par vidéo ou par image est une logique du type, et le code du type
  ne tourne que d'un seul côté.
- **`process`** puis **`write`**, qui traitent un chunk et en écrivent le résultat. Séparés
  parce qu'ils échouent différemment — un appel d'inférence est transitoire et se rejoue, une
  écriture ne doit jamais être partielle.

`write` doit être **idempotent**. Les résultats vont dans LanceDB tandis que l'avancement va
dans PostgreSQL : les deux écritures ne peuvent pas partager une transaction, donc un worker
qui meurt entre les deux refera le chunk. Un identifiant dérivé du job et du rang du chunk
suffit à rendre le rejeu inoffensif.
"""

from abc import ABC, abstractmethod
from typing import Any, Generic, Iterable, TypeVar

from pydantic import BaseModel, ConfigDict

from ..writer import JobWriter


class JobParams(BaseModel):
    """Base des paramètres d'un type de job.

    `extra="forbid"` n'est pas un détail de rigueur : c'est lui qui fait émettre
    `additionalProperties: false` dans le schéma JSON publié, donc lui qui permet à
    l'application de refuser un nom de paramètre mal orthographié. Sans ça, une faute de
    frappe passe la validation et le paramètre est ignoré en silence à l'exécution.
    """

    model_config = ConfigDict(extra="forbid")


ParamsT = TypeVar("ParamsT", bound=JobParams)


class Chunk(BaseModel):
    """Un lot de tâches tel qu'un planificateur le produit.

    Attributes:
        payload: Ce que le type devra traiter. Opaque pour le moteur.
        task_count: Nombre de tâches, pour la progression.
    """

    payload: dict[str, Any]
    task_count: int


class JobKind(ABC, Generic[ParamsT]):
    """Un type de traitement exécutable sur un dataset."""

    name: str
    params_model: type[ParamsT]

    #: Ce que produit ce type, dans le vocabulaire de provenance des schémas Pixano. La
    #: plupart des types font tourner un modèle ; un type qui n'en fait pas tourner doit le
    #: dire, pour qu'on ne prenne pas sa sortie pour une prédiction.
    source_type: str = "model"

    @abstractmethod
    def plan(self, dataset_id: str, params: ParamsT) -> Iterable[Chunk]:
        """Découper le travail du job en chunks.

        Args:
            dataset_id: Le dataset visé.
            params: Les paramètres validés.

        Returns:
            Les chunks, dans l'ordre d'exécution voulu.
        """

    @abstractmethod
    def process(self, payload: dict[str, Any], params: ParamsT) -> Any:
        """Traiter un chunk et renvoyer son résultat, sans rien écrire.

        C'est ici que vivent les appels à l'inférence. Un échec transitoire doit être rejoué
        ici même : le moteur ne rejoue que les chunks dont le worker est mort.
        """

    @abstractmethod
    def write(self, writer: "JobWriter", result: Any, payload: dict[str, Any], params: ParamsT) -> None:
        """Écrire le résultat, de façon idempotente.

        Le type ne sait pas ouvrir un dataset : il reçoit un écrivain, qui est le seul point
        d'écriture du système. C'est ce qui rendra possible, plus tard, de sérialiser les
        écritures d'un dataset entre plusieurs workers sans toucher au moindre type de job.

        Args:
            writer: Par où écrire, déjà lié au dataset et au job.
            result: Ce que `process` a renvoyé.
            payload: Le chunk traité.
            params: Les paramètres validés.
        """

    def params_schema(self) -> dict[str, Any]:
        """Le schéma JSON des paramètres, publié pour l'application."""
        return self.params_model.model_json_schema()

    def validate_params(self, raw: dict[str, Any]) -> ParamsT:
        """Relire les paramètres stockés en base."""
        return self.params_model.model_validate(raw)
