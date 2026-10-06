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

Les échecs se classent en trois familles, et le moteur traite chacune différemment :

- **transitoire** — le service est saturé, redémarre, ne répond pas. Le type lève
  `TransientError` ; le moteur rend le chunk à la file après un délai croissant, et ne l'écarte
  qu'après plusieurs tentatives.
- **d'item** — un item précis est illisible, les autres vont bien. Le type ne lève rien : il
  termine le chunk et déclare l'item dans son bilan (`outcome`), qui le met en quarantaine.
- **fatale** — toute autre exception. Le chunk est en échec, et le job avec lui.

`write` doit être **idempotent**. Les résultats vont dans LanceDB tandis que l'avancement va
dans PostgreSQL : les deux écritures ne peuvent pas partager une transaction, donc un worker
qui meurt entre les deux refera le chunk. Un identifiant dérivé du job et du rang du chunk
suffit à rendre le rejeu inoffensif.
"""

from abc import ABC, abstractmethod
from typing import Any, Generic, Iterable, TypeVar

from pydantic import BaseModel, ConfigDict, Field

from ..reader import JobReader
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


class TransientError(Exception):
    """Un échec de circonstance : le même chunk, rejoué plus tard, a toutes les chances de passer.

    À lever quand le type a épuisé ses propres reprises courtes — un appel qui échoue une
    seconde puis passe n'a pas à faire le tour de la file.
    """


class QuarantinedItem(BaseModel):
    """Un item qu'un type de job n'a pas su traiter.

    Attributes:
        item_id: L'identifiant de l'item dans le dataset.
        reason: Ce qui s'est passé, lisible par la personne qui ouvrira la quarantaine. **En
            anglais** : l'interface l'affiche tel quel, et elle est en anglais. Le code reste
            commenté en français, ce texte-là ne l'est pas parce qu'il n'est pas lu ici.
        detail: De quoi diagnostiquer, sans limite de forme.
    """

    item_id: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    detail: dict[str, Any] | None = None


class Outcome(BaseModel):
    """Le bilan d'un chunk : ce que ses tâches sont devenues.

    Chaque tâche est dans exactement une des trois catégories, et le moteur le vérifie : un
    bilan qui ne tombe pas juste est un défaut du type, pas un détail d'affichage.

    Attributes:
        produced: Tâches qui ont donné un résultat.
        skipped: Tâches sans objet — un enregistrement sans image, pour un calcul sur les
            images. Ce n'est pas un échec, et rien ne va en quarantaine.
        quarantined: Tâches en échec, une par item.
    """

    produced: int = Field(ge=0)
    skipped: int = Field(default=0, ge=0)
    quarantined: list[QuarantinedItem] = Field(default_factory=list)

    @property
    def total(self) -> int:
        """Le nombre de tâches que ce bilan couvre."""
        return self.produced + self.skipped + len(self.quarantined)


class JobKind(ABC, Generic[ParamsT]):
    """Un type de traitement exécutable sur un dataset."""

    name: str
    params_model: type[ParamsT]

    #: Ce que produit ce type, dans le vocabulaire de provenance des schémas Pixano. La
    #: plupart des types font tourner un modèle ; un type qui n'en fait pas tourner doit le
    #: dire, pour qu'on ne prenne pas sa sortie pour une prédiction.
    source_type: str = "model"

    def prepare(self, writer: "JobWriter", params: ParamsT) -> None:
        """Mettre le dataset en état avant que le job ne soit découpé.

        Appelé une fois par job, sous le bail de planification, avant `plan` — jamais par le
        rejeu d'un chunk ni par la relance d'un job qui a déjà ses chunks. Ne rien faire est le
        défaut, et c'est ce que font la plupart des types : un type ne redéfinit ceci que pour
        une remise en état que ses chunks ne peuvent pas faire chacun pour soi — vider une table
        avant de la remplir, par exemple.

        Trois règles, vérifiées par la suite de contrat pour les deux premières :

        - **Idempotent.** Appelé deux fois, le dataset est dans le même état qu'après une fois :
          un planificateur mort après `prepare` laisse son bail expirer, et le suivant repart.
        - **Ne détruit rien sans qu'un paramètre explicite le demande.** Un job lancé avec les
          paramètres par défaut ne doit jamais perdre ce que le dataset contient.
        - **Pas de `finalize` en face**, tant qu'aucun type n'en a besoin : ce qui doit se faire
          en fin de job se conçoit alors, pas par symétrie.

        Args:
            writer: Par où écrire, déjà lié au dataset et au job.
            params: Les paramètres validés.
        """

    @abstractmethod
    def plan(self, reader: "JobReader", params: ParamsT) -> Iterable[Chunk]:
        """Découper le travail du job en chunks.

        Le lecteur est symétrique de l'écrivain que reçoit `write` : un type énumère ce qu'il
        va traiter sans ouvrir de dataset lui-même. Un type qui n'a rien à lire — son travail
        tient dans ses paramètres — peut simplement l'ignorer.

        Args:
            reader: Par où lire le dataset visé.
            params: Les paramètres validés.

        Returns:
            Les chunks, dans l'ordre d'exécution voulu.
        """

    @abstractmethod
    def process(self, reader: "JobReader", payload: dict[str, Any], params: ParamsT) -> Any:
        """Traiter un chunk et renvoyer son résultat, sans rien écrire.

        C'est ici que vivent les appels à l'inférence. Un échec transitoire bref se rejoue ici
        même ; un échec qui dure se signale par `TransientError`, et le moteur rejouera le
        chunk plus tard. Un item illisible ne doit pas faire échouer le chunk : il se déclare
        dans le bilan que rend `outcome`.

        Le lecteur est celui de `plan`. Il en faut un ici aussi : un chunk porte de quoi
        désigner le travail, jamais les données elles-mêmes — mettre des images encodées dans
        un payload gonflerait la table des chunks de tout le poids du dataset.
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

    def outcome(self, result: Any, payload: dict[str, Any], task_count: int) -> Outcome:
        """Dire ce que les tâches du chunk sont devenues.

        Par défaut, toutes ont produit un résultat. Un type qui écarte ou met en quarantaine
        des items le redéfinit : c'est ce qui permet à un job de dire ce qu'il a produit, et
        pas seulement ce qu'il a tenté.

        Args:
            result: Ce que `process` a renvoyé.
            payload: Le chunk traité.
            task_count: Le nombre de tâches du chunk, que le bilan doit couvrir exactement.
        """
        return Outcome(produced=task_count)

    def params_schema(self) -> dict[str, Any]:
        """Le schéma JSON des paramètres, publié pour l'application."""
        return self.params_model.model_json_schema()

    def validate_params(self, raw: dict[str, Any]) -> ParamsT:
        """Relire les paramètres stockés en base."""
        return self.params_model.model_validate(raw)
