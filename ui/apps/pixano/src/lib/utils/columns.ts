/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

/**
 * Human-readable label for a record column name.
 *
 * Replaces every underscore, trims the leading one from system columns like
 * `_distance`, and Title-Cases each word: `created_at` → "Created At",
 * `_distance` → "Distance".
 */
export function formatColumnLabel(name: string): string {
  return name
    .replace(/^_+/, "")
    .replaceAll("_", " ")
    .trim()
    .split(/\s+/)
    .map((word) => (word ? word[0].toUpperCase() + word.slice(1) : word))
    .join(" ");
}
