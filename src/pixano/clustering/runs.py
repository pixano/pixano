# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""What a dataset keeps of each run of a clustering (backend-processing §24).

Each run is kept: its rows hold the records' clusters, and its entry says how they were made —
the algorithm and its parameters, the embeddings read, how many groups came out —, from which a
person reads its name (`Clustering.label`).
"""

from collections.abc import Mapping
from datetime import timezone
from enum import Enum

from pydantic import AwareDatetime, BaseModel, ConfigDict

from pixano.schemas import NOISE_CLUSTER


class ClusteringAlgorithm(str, Enum):
    """How the records are grouped.

    Attributes:
        KMEANS: Into as many groups as asked, every record in one.
        HDBSCAN: Into as many groups as the vectors hold, dense enough for their size; the records
            between them belong to none (`pixano.schemas.NOISE_CLUSTER`).
    """

    KMEANS = "kmeans"
    HDBSCAN = "hdbscan"


#: How a run's name calls each algorithm.
ALGORITHM_NAMES = {ClusteringAlgorithm.KMEANS: "K-Means", ClusteringAlgorithm.HDBSCAN: "HDBSCAN"}


class Clustering(BaseModel):
    """A run of a clustering, as a dataset keeps it.

    Attributes:
        run_id: The run: the job that grouped the records. Its rows carry it.
        algorithm: How the records were grouped.
        parameters: The algorithm's parameters the run was given: `clusters` for K-Means,
            `min_cluster_size` for HDBSCAN.
        model: The embeddings model whose vectors were grouped.
        clusters: How many groups the run made, noise aside.
        noise: How many records no group took in.
        records: How many records were grouped: those with an embedding.
        computed_at: When the run wrote its clusters, with its time zone.
    """

    model_config = ConfigDict(frozen=True)

    run_id: str
    algorithm: ClusteringAlgorithm
    parameters: dict[str, int | float | str | bool]
    model: str
    clusters: int
    noise: int
    records: int
    computed_at: AwareDatetime

    def counted(self, groups: Mapping[str, int]) -> "Clustering":
        """The run, its counts those of these groups.

        Args:
            groups: Each record's group in the run, `NOISE_CLUSTER` for a record in none.
        """
        return self.model_copy(
            update={
                "clusters": len(set(groups.values()) - {NOISE_CLUSTER}),
                "noise": sum(1 for group in groups.values() if group == NOISE_CLUSTER),
                "records": len(groups),
            }
        )

    @property
    def label(self) -> str:
        """How a person reads the run: its algorithm, what it was asked, and when, in UTC — the server
        does not know the reader's time zone.
        """
        if self.algorithm is ClusteringAlgorithm.KMEANS:
            asked: str | None = f"{self.parameters.get('clusters', self.clusters)} groups"
        else:
            size = self.parameters.get("min_cluster_size")
            asked = f"groups of {size} or more" if size is not None else None
        when = f"{self.computed_at.astimezone(timezone.utc):%Y-%m-%d %H:%M} UTC"
        return ", ".join(part for part in (f"Clusters — {ALGORITHM_NAMES[self.algorithm]}", asked, when) if part)
