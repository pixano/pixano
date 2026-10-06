# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Préparer les deux datasets de la démo de l'étape 1, sur n'importe quelle machine.

La démo ne dépend d'aucune bibliothèque d'exemples : les images sont générées ici, de façon
déterministe, puis importées par la CLI Pixano — le chemin qu'emprunterait un utilisateur. Deux
datasets, chacun pour une partie de la démo :

- **Demo shapes** : 400 images embarquées dans LanceDB (mode `embed`, celui d'un import par
  défaut). Sur une inférence CPU, le calcul d'embeddings y dure deux à trois minutes : assez pour
  voir la progression, annuler, et tuer le worker en plein travail.
- **Demo damaged images** : 60 images référencées par chemin (mode `uri`), dont deux corrompues
  et une supprimée après l'import. C'est sur lui que se montre la quarantaine.

Rejouable : chaque exécution écrase les deux datasets et régénère les mêmes images.

Usage :
    uv run --directory packages/pixano-worker python scripts/prepare_demo.py

Par défaut, les datasets vont dans `data/` à la racine du dépôt — les valeurs de `.env.example`.
Les chemins par défaut sont calculés depuis l'emplacement de ce script et non depuis le
répertoire courant, que `uv run --directory` déplace.
"""

import argparse
import json
import random
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw


SHAPES_NAME = "Demo shapes"
SHAPES_COUNT = 400

DEFECTS_NAME = "Demo damaged images"
DEFECTS_COUNT = 60
DEFECTS_FOLDER = "demo_defects"
# Ce que la démo annonce : deux images illisibles et une absente, donc 57 vecteurs sur 60.
CORRUPTED = (10, 11)
DELETED = 40

IMAGE_SIZE = 224
# Les graines fixent les images : deux préparations donnent le même dataset, et la démo annonce
# les mêmes chiffres chez tout le monde.
SHAPES_SEED = 2026
DEFECTS_SEED = 1789

REPO_ROOT = Path(__file__).resolve().parents[3]

# Le chemin sous lequel le worker voit le dossier des médias — dans le compose, le volume monté
# en /medias. Les images du dataset par chemin sont référencées sous cette racine : c'est
# PIXANO_MEDIA_ROOT du worker, quel que soit l'endroit d'où on le lance.
COMPOSE_MEDIA_ROOT = "/medias"


def draw_images(target: Path, count: int, seed: int) -> list[Path]:
    """Dessiner des formes colorées, différentes d'une image à l'autre.

    Des formes plutôt que du bruit : un modèle comme CLIP en tire des vecteurs distincts, ce qui
    rend le résultat vérifiable, et elles pèsent quelques kilo-octets.
    """
    rng = random.Random(seed)
    target.mkdir(parents=True, exist_ok=True)
    paths = []
    for index in range(count):
        background = tuple(rng.randint(180, 255) for _ in range(3))
        image = Image.new("RGB", (IMAGE_SIZE, IMAGE_SIZE), background)
        pen = ImageDraw.Draw(image)
        for _ in range(rng.randint(1, 4)):
            colour = tuple(rng.randint(0, 200) for _ in range(3))
            x0, y0 = rng.randint(0, IMAGE_SIZE - 60), rng.randint(0, IMAGE_SIZE - 60)
            x1, y1 = x0 + rng.randint(30, 150), y0 + rng.randint(30, 150)
            shape = rng.choice(("ellipse", "rectangle", "triangle"))
            if shape == "ellipse":
                pen.ellipse((x0, y0, x1, y1), fill=colour)
            elif shape == "rectangle":
                pen.rectangle((x0, y0, x1, y1), fill=colour)
            else:
                pen.polygon([(x0, y1), ((x0 + x1) // 2, y0), (x1, y1)], fill=colour)
        path = target / f"forme-{index:04d}.jpg"
        image.save(path, quality=90)
        paths.append(path)
    return paths


def pixano_import(data_dir: Path, source: Path, extra: list[str]) -> str:
    """Importer par la CLI Pixano, comme le ferait un utilisateur.

    Returns:
        La dernière ligne de la CLI, qui nomme le dataset créé.
    """
    cli = Path(sys.executable).parent / "pixano"
    command = [str(cli), "data", "import", str(data_dir), str(source), "--workspace", "image", "--yes", *extra]
    completed = subprocess.run(command, capture_output=True, text=True)
    if completed.returncode != 0:
        raise SystemExit(f"l'import a échoué :\n{completed.stdout}\n{completed.stderr}")
    lines = [line for line in completed.stdout.splitlines() if "imported successfully" in line]
    return lines[-1] if lines else completed.stdout.strip().splitlines()[-1]


def remove_previous(data_dir: Path, name: str) -> None:
    """Supprimer un dataset de la démo déjà présent.

    Plutôt que le mode `overwrite` de l'import : repartir d'un dossier vide garantit qu'aucune
    table laissée par une démo précédente — les embeddings, surtout — ne survive à la préparation.
    Seuls les datasets qui portent exactement le nom de la démo sont touchés.
    """
    library = data_dir / "library"
    if not library.is_dir():
        return
    for info_path in library.glob("*/info.json"):
        if json.loads(info_path.read_text()).get("name") == name:
            shutil.rmtree(info_path.parent)


def dataset_id(data_dir: Path, name: str) -> str:
    """L'identifiant du dataset qui porte ce nom, pour le retrouver dans l'API et les journaux."""
    for info_path in (data_dir / "library").glob("*/info.json"):
        info = json.loads(info_path.read_text())
        if info.get("name") == name:
            return info["id"]
    raise SystemExit(f"dataset introuvable après import : {name}")


def prepare_shapes(data_dir: Path) -> str:
    """Générer et importer le dataset embarqué ; rendre son identifiant."""
    remove_previous(data_dir, SHAPES_NAME)
    with tempfile.TemporaryDirectory() as scratch:
        source = Path(scratch)
        draw_images(source, SHAPES_COUNT, SHAPES_SEED)
        pixano_import(data_dir, source, ["--name", SHAPES_NAME, "--media", "embed"])
    return dataset_id(data_dir, SHAPES_NAME)


def prepare_defects(data_dir: Path, media_dir: Path, media_root: str) -> str:
    """Générer, importer par chemin puis abîmer le dataset de la quarantaine ; rendre son identifiant.

    Args:
        data_dir: La bibliothèque de datasets.
        media_dir: Où écrire les images, tel que cette machine le voit.
        media_root: Le même dossier, tel que le worker le verra : le préfixe des chemins importés.
    """
    remove_previous(data_dir, DEFECTS_NAME)
    folder = media_dir / DEFECTS_FOLDER
    shutil.rmtree(folder, ignore_errors=True)
    paths = draw_images(folder, DEFECTS_COUNT, DEFECTS_SEED)

    with tempfile.TemporaryDirectory() as scratch:
        spec = Path(scratch) / "dataset.yaml"
        spec.write_text(
            "pixano: 2\n"
            "dataset:\n"
            f'  name: "{DEFECTS_NAME}"\n'
            "  workspace: image\n"
            "format: pixano_jsonl\n"
            "media:\n"
            "  mode: uri\n"
            f"  uri_prefix: {media_root}/{DEFECTS_FOLDER}\n"
        )
        pixano_import(data_dir, folder, ["--spec", str(spec), "--media", "uri"])

    # Abîmées après l'import. En mode `uri`, l'import ne lit pas les images aujourd'hui — il les
    # référence sans en connaître la taille — mais la démo veut que le défaut soit rencontré par
    # le calcul d'embeddings, pas par un import qui se mettrait un jour à les valider.
    for index in CORRUPTED:
        paths[index].write_bytes(b"ceci n'est pas une image " * 100)
    paths[DELETED].unlink()
    return dataset_id(data_dir, DEFECTS_NAME)


def main() -> None:
    """Préparer les deux datasets et dire quoi faire ensuite."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data-dir", type=Path, default=REPO_ROOT / "data", help="PIXANO_DATA_DIR du compose.")
    parser.add_argument(
        "--media-dir", type=Path, default=REPO_ROOT / "data" / "media", help="PIXANO_MEDIA_DIR du compose."
    )
    parser.add_argument(
        "--media-root",
        default=COMPOSE_MEDIA_ROOT,
        help="Le dossier des médias tel que le worker le voit, c'est-à-dire son PIXANO_MEDIA_ROOT. "
        "Par défaut le montage du compose ; pour un worker lancé à la main, donner --media-dir lui-même.",
    )
    args = parser.parse_args()

    data_dir, media_dir = args.data_dir.resolve(), args.media_dir.resolve()
    (data_dir / "library").mkdir(parents=True, exist_ok=True)

    print(f"bibliothèque : {data_dir / 'library'}", flush=True)
    print(f"« {SHAPES_NAME} » : {SHAPES_COUNT} images embarquées…", flush=True)
    shapes = prepare_shapes(data_dir)
    print(f"« {DEFECTS_NAME} » : {DEFECTS_COUNT} images par chemin, dont 3 abîmées…", flush=True)
    defects = prepare_defects(data_dir, media_dir, args.media_root)

    print(f"prêt — « {SHAPES_NAME} » ({shapes}) et « {DEFECTS_NAME} » ({defects}).")


if __name__ == "__main__":
    main()
