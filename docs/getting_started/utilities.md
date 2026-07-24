# Utilities

## Fix dataset creation date

The `fix-dataset-creation-date.py` script resolves datasets that have an empty `creation_date` in their `info.json`. It fills the missing date using the oldest item's `created_at` timestamp from the dataset.

### Why this is needed

Datasets created before v0.6.13 may not have a `creation_date` field set. The home page sorts datasets by creation date and displays it on each card — without it, datasets appear without a date and are pushed to the end of the list.

### Usage

```bash
# Fix all datasets with empty creation_date
python fix-dataset-creation-date.py /path/to/library

# Fix a specific dataset by ID
python fix-dataset-creation-date.py /path/to/library --dataset-id my_dataset

# Overwrite existing creation_date values
python fix-dataset-creation-date.py /path/to/library --overwrite
```

### Options

| Argument | Description |
|----------|-------------|
| `library_dir` | Path to the dataset library directory (required). |
| `--dataset-id`, `-d` | Fix only the dataset with this ID. |
| `--overwrite`, `-f` | Overwrite existing `creation_date` values (default: skip datasets that already have one). |

### Behavior

1. Scans `info.json` files in the library directory.
2. Skips datasets that already have a `creation_date` (unless `--overwrite` is used).
3. Creates a backup (`info.json.bak`) before modifying any file.
4. Queries the oldest item's `created_at` timestamp and writes it as the creation date (format: `YYYY-MM-DD`).
5. Restores the backup automatically if an error occurs during processing.
