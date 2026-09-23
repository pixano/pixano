/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

/** The library page's dataset ordering. */

export type DatasetSortMode = "name" | "creation_date";

interface SortableDataset {
  name: string;
  creation_date: string; // ISO string, or "" for datasets predating the field
}

/**
 * Sort datasets for the library grid.
 *
 * Name mode: alphabetical. Date mode: NEWEST first (ISO strings compare
 * chronologically); datasets without a creation_date (imported before the
 * field existed and not yet backfilled by `pixano dataset
 * fix-creation-dates`) sort LAST, alphabetically among themselves.
 */
export function sortDatasets<T extends SortableDataset>(list: T[], mode: DatasetSortMode): T[] {
  return [...list].sort((a, b) => {
    if (mode === "name") return a.name.localeCompare(b.name);
    if (!a.creation_date && !b.creation_date) return a.name.localeCompare(b.name);
    if (!a.creation_date) return 1;
    if (!b.creation_date) return -1;
    return b.creation_date.localeCompare(a.creation_date);
  });
}
