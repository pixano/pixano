# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Fix empty creation_date in dataset info.json using oldest item's created_at.

This script finds datasets with empty creation_date and fills it with the
creation date of the oldest item in the dataset. A backup of the original
info.json is created before modification.

Usage:
    # Fix all datasets with empty creation_date
    python fix-dataset-creation-date.py /path/to/library

    # Fix specific dataset
    python fix-dataset-creation-date.py /path/to/library --dataset-id my_dataset

    # Overwrite existing dates
    python fix-dataset-creation-date.py /path/to/library --overwrite
"""

import argparse
import shutil
import sys
from pathlib import Path


# Add project root to path if needed
project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from pixano.datasets.dataset import Dataset  # noqa: E402
from pixano.datasets.dataset_info import DatasetInfo  # noqa: E402


def fix_creation_date(library_dir: Path, dataset_id: str | None, overwrite: bool) -> None:
    """Fix creation_date for datasets.

    Args:
        library_dir: Path to the dataset library directory.
        dataset_id: If provided, fix only this dataset.
        overwrite: If True, overwrite existing creation_date.
    """
    if not library_dir.exists():
        print(f"Error: Library directory '{library_dir}' does not exist.")
        sys.exit(1)

    # Find all datasets
    info_files = list(library_dir.glob("*/info.json"))
    if not info_files:
        print(f"No datasets found in '{library_dir}'.")
        sys.exit(1)

    fixed_count = 0
    skipped_count = 0

    for info_path in info_files:
        try:
            info = DatasetInfo.from_json(info_path)
        except Exception as e:
            print(f"Error reading {info_path}: {e}")
            continue

        # Filter by dataset_id if provided
        if dataset_id and info.id != dataset_id:
            continue

        dataset_name: str = info.name

        # Skip if date exists and --overwrite not set
        if info.creation_date and not overwrite:
            print(f"Skipping '{dataset_name}' with id='{info.id}': creation_date already set ({info.creation_date})")
            skipped_count += 1
            continue

        # Backup info.json
        backup_path = info_path.with_suffix(".json.bak")
        if backup_path.exists():
            print(f"Warning: Backup already exists at '{backup_path}', overwriting.")
        shutil.copy2(info_path, backup_path)

        try:
            # Open dataset and get oldest item
            dataset = Dataset(info_path.parent)
            oldest_items = dataset.get_data("item", limit=1, sortcol="created_at", order="asc")

            if oldest_items:
                oldest_date = oldest_items[0].created_at.strftime("%Y-%m-%d")
                info.creation_date = oldest_date
                info.to_json(info_path)
                print(f"Fixed '{dataset_name}' with id='{info.id}': creation_date = {oldest_date}")
                fixed_count += 1
            else:
                print(f"Warning: dataset '{dataset_name}' with id='{info.id}' has no items, skipping.")
                # Restore backup since we didn't modify
                shutil.copy2(backup_path, info_path)
                skipped_count += 1
        except Exception as e:
            print(f"Error processing '{dataset_name}' with id='{info.id}': {e}")
            # Restore backup on error
            if backup_path.exists():
                shutil.copy2(backup_path, info_path)
            skipped_count += 1

    print(f"\nDone: {fixed_count} fixed, {skipped_count} skipped.")


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "library_dir",
        type=Path,
        help="Path to the dataset library directory.",
    )
    parser.add_argument(
        "--dataset-id",
        "-d",
        type=str,
        default=None,
        help="Fix only the dataset with this ID.",
    )
    parser.add_argument(
        "--overwrite",
        "-f",
        action="store_true",
        default=False,
        help="Overwrite existing creation_date (default: skip datasets with non-empty creation_date).",
    )
    args = parser.parse_args()

    fix_creation_date(args.library_dir, args.dataset_id, args.overwrite)


if __name__ == "__main__":
    main()
