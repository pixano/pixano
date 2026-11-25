# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""The table that holds the clusters a dataset's records were grouped into: one row per run and record.

A clustering groups the records by their embeddings, and each run of it is kept: its rows are the
record's cluster in that run, in long form, so that a run adds rows and never columns. What a run
was — its algorithm, its parameters, the embeddings it read — is in the dataset's
`DatasetInfo.clusterings` (backend-processing §24).
"""

from pixano.utils import issubclass_strict

from .records import RecordComponent


#: The cluster of a record no group took in: HDBSCAN's noise. K-Means puts every record in a group.
NOISE_CLUSTER = -1


class RecordClusters(RecordComponent):
    """The cluster of a record in one run of a clustering.

    Its identifier is the run's, then the record's (`record_cluster_id`).

    Attributes:
        run_id: The run: the job that grouped the records.
        cluster: The record's group in that run, numbered from 0 by decreasing size;
            `NOISE_CLUSTER` for a record no group took in.
    """

    run_id: str = ""
    cluster: int = NOISE_CLUSTER


def record_cluster_id(run_id: str, record_id: str) -> str:
    """The identifier of a record's row in a run: one row per run and record, whatever the run wrote before."""
    return f"{run_id}:{record_id}"


def is_clusters(cls: type, strict: bool = False) -> bool:
    """Check if a class is the schema of the records' clusters."""
    return issubclass_strict(cls, RecordClusters, strict)
