# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

r"""Mesurer le débit du job d'embeddings, par taille de lot et par mode de stockage.

La question à laquelle ce script répond n'est pas « combien d'images par seconde » — cela
dépend du modèle et de la machine — mais deux comparaisons qui, elles, se transposent :

1. **Ce que coûte le transport des octets.** Le plan pose que les médias ne doivent pas
   transiter par Pixano. Sur deux datasets portant les mêmes images, l'un référencé par
   chemin et l'autre embarqué, l'écart chiffre cet invariant au lieu de l'affirmer.
2. **La taille de lot qui vaut le coup.** Un lot amortit un aller-retour réseau et un
   passage de modèle ; trop gros, il rallonge ce qu'une reprise doit refaire.

Une tâche est un enregistrement **planifié**, pas un vecteur produit : le type de job écarte
les enregistrements sans image exploitable. Les deux nombres ne coïncident que sur un dataset
où chaque enregistrement porte une image — mesuré sur nuScenes, 26 766 tâches ne donnent que
404 vecteurs, le reste étant des relevés lidar sans caméra. D'où le choix des datasets à
mesurer, explicite et obligatoire : un débit n'a de sens que sur un dataset entièrement imagé.

Usage :
    uv run --directory packages/pixano-worker python scripts/measure_throughput.py \\
        --api http://localhost:7492 --sizes 8,16,32,64 \\
        --datasets "VOC 2007 Sample,VOC 2007 (uri)"
"""

import argparse
import json
import re
import time
import urllib.error
import urllib.request
from pathlib import Path


def _call(url: str, payload: dict | None = None) -> dict:
    data = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"} if data else {})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read())


#: Ce que le type d'embeddings journalise pour chaque chunk écrit, avec l'identifiant du job.
PHASES = re.compile(
    r"job (?P<job>[0-9a-f-]{36}) : phases lecture (?P<read>[\d.]+) s, inférence (?P<inference>[\d.]+) s, "
    r"écriture (?P<write>[\d.]+) s"
)


def phases_of(worker_log: Path, job_id: str) -> dict[str, float]:
    """Additionner, sur le journal du worker, le temps passé par phase pour un job.

    Les phases sont sommées sur les chunks : avec plusieurs chunks en vol, leur somme dépasse
    la durée du job. Ce sont des temps de travail, pas des temps d'attente — c'est ce qui dit où
    va le temps quand un lot plus gros se révèle plus lent.
    """
    totals = {"read": 0.0, "inference": 0.0, "write": 0.0}
    for line in worker_log.read_text(errors="replace").splitlines():
        found = PHASES.search(line)
        if found and found["job"] == job_id:
            for phase in totals:
                totals[phase] += float(found[phase])
    return totals


def run_job(api: str, dataset_id: str, chunk_size: int, poll_s: float = 0.2) -> tuple[float, int, str]:
    """Lancer un job d'embeddings et attendre sa fin.

    L'attente est courte devant la durée d'un job, pour que le pas de scrutation ne se
    confonde pas avec ce qu'on mesure.

    Returns:
        La durée en secondes, le nombre de tâches planifiées, et l'identifiant du job.
    """
    job = _call(
        f"{api}/jobs",
        {
            "kind": "embeddings",
            "dataset_id": dataset_id,
            "params": {"model": "clip", "chunk_size": chunk_size},
        },
    )
    started = time.monotonic()
    while True:
        time.sleep(poll_s)
        state = _call(f"{api}/jobs/{job['id']}")
        if state["state"] in ("done", "error", "cancelled"):
            if state["state"] != "done":
                raise RuntimeError(f"job {state['state']} : {state}")
            return time.monotonic() - started, state["total_tasks"], job["id"]


def datasets(api: str) -> dict[str, str]:
    """Les datasets disponibles, par nom."""
    return {d["name"]: d["id"] for d in _call(f"{api}/datasets")}


def main() -> None:
    """Mesurer et rendre un tableau prêt à coller dans la documentation."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api", default="http://localhost:7492")
    parser.add_argument("--sizes", default="8,16,32,64")
    parser.add_argument(
        "--datasets",
        required=True,
        help="Noms des datasets à mesurer, séparés par des virgules. Obligatoire : mesurer "
        "tout ce qui traîne dans la bibliothèque lance un calcul long sur des datasets dont "
        "le débit ne veut rien dire.",
    )
    parser.add_argument(
        "--worker-log",
        type=Path,
        help="Journal du worker (par exemple la sortie de `docker compose logs -f pixano-worker`, ou celle "
        "d'un worker lancé à la main), pour ventiler la durée par phase : lecture, inférence, écriture.",
    )
    args = parser.parse_args()

    available = datasets(args.api)
    wanted = [n.strip() for n in args.datasets.split(",") if n.strip()]
    unknown = [name for name in wanted if name not in available]
    if unknown:
        raise SystemExit(f"dataset inconnu : {', '.join(unknown)}. Connus : {', '.join(available)}")
    sizes = [int(s) for s in args.sizes.split(",")]

    phases = " lecture | inférence | écriture |" if args.worker_log else ""
    print(f"| dataset | lot | tâches planifiées | durée | tâches/s |{phases}", flush=True)
    print("| --- | ---: | ---: | ---: | ---: |" + (" ---: | ---: | ---: |" if args.worker_log else ""), flush=True)
    for name in wanted:
        for size in sizes:
            elapsed, tasks, job_id = run_job(args.api, available[name], size)
            rate = tasks / elapsed if elapsed else 0.0
            row = f"| {name} | {size} | {tasks} | {elapsed:.1f} s | {rate:.1f} |"
            if args.worker_log:
                # Le worker écrit son journal après coup ; lui laisser le temps de le vider.
                time.sleep(1.0)
                totals = phases_of(args.worker_log, job_id)
                row += f" {totals['read']:.1f} s | {totals['inference']:.1f} s | {totals['write']:.1f} s |"
            print(row, flush=True)


if __name__ == "__main__":
    main()
