# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Mesurer ce que coûte la compaction d'une table d'annotations, sous le verrou d'écriture.

La compaction tourne toutes les `COMPACT_EVERY_WRITES` écritures, dans le chunk qui la déclenche,
sous le verrou d'écriture du dataset : les autres chunks du même dataset attendent qu'elle
finisse. Courte sur une table de vecteurs (63 fragments fusionnés en une fraction de seconde),
elle n'avait pas été mesurée sur une table d'annotations — celle que les types de l'étape 2
rempliront, et que les utilisateurs annotent en même temps.

Le script remplit une table de classifications par écritures de la taille d'un chunk, comme
le ferait un job, et chronomètre chaque `optimize` : c'est le temps pendant lequel le dataset
n'accepte aucune autre écriture.

Usage :
    uv run --directory packages/pixano-worker python scripts/measure_compaction.py --rows 10000,30000
"""

import argparse
import statistics
import tempfile
import time
from pathlib import Path

from pixano_worker.writer import COMPACT_EVERY_WRITES, KEEP_OLD_VERSIONS_FOR

from pixano.datasets import Dataset
from pixano.datasets.dataset_info import DatasetInfo
from pixano.schemas.annotations.classification import Classification
from pixano.schemas.records import Record


# La taille d'un chunk d'annotations : une ligne par enregistrement, huit enregistrements par
# chunk comme le défaut du type d'embeddings.
ROWS_PER_WRITE = 8


def measure(rows: int, root: Path) -> tuple[int, list[float]]:
    """Remplir une table par écritures de chunk, compacter au rythme du writer, chronométrer.

    Returns:
        Le nombre de compactions, et la durée de chacune en secondes.
    """
    dataset = Dataset.create(
        root / f"compaction-{rows}",
        DatasetInfo(id=f"compaction-{rows}", name="Compaction", record=Record, classification=Classification),
    )
    dataset.add_data("records", [Record(id=f"rec-{n}") for n in range(rows)])

    durations: list[float] = []
    writes = 0
    for start in range(0, rows, ROWS_PER_WRITE):
        batch = [
            Classification(id=f"cls-{n}", record_id=f"rec-{n}", labels=["a"], confidences=[1.0])
            for n in range(start, min(start + ROWS_PER_WRITE, rows))
        ]
        dataset.update_data("classifications", batch)
        writes += 1
        if writes % COMPACT_EVERY_WRITES == 0:
            began = time.perf_counter()
            dataset.open_table("classifications").optimize(cleanup_older_than=KEEP_OLD_VERSIONS_FOR)
            durations.append(time.perf_counter() - began)
    return writes, durations


def main() -> None:
    """Mesurer et rendre un tableau prêt à coller dans la documentation."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--rows", default="10000,30000", help="Tailles de table à mesurer, en lignes.")
    args = parser.parse_args()

    print("| lignes | écritures | compactions | médiane | max | dernière |", flush=True)
    print("| ---: | ---: | ---: | ---: | ---: | ---: |", flush=True)
    with tempfile.TemporaryDirectory() as scratch:
        for rows in (int(r) for r in args.rows.split(",")):
            writes, durations = measure(rows, Path(scratch))
            print(
                f"| {rows} | {writes} | {len(durations)} | {statistics.median(durations):.3f} s "
                f"| {max(durations):.3f} s | {durations[-1]:.3f} s |",
                flush=True,
            )


if __name__ == "__main__":
    main()
