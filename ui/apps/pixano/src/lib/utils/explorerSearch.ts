/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

/** How the explorer shows the records: a gallery, a table, or the overview of them all. */
export type ExplorerView = "grid" | "table" | "overview";

/** Every view of the explorer, as a URL or a remembered choice names it. */
export const EXPLORER_VIEWS: readonly ExplorerView[] = ["grid", "table", "overview"];

/** Whether a name read from a URL or from storage is a view of the explorer. */
export function isExplorerView(view: string | null): view is ExplorerView {
  return view !== null && (EXPLORER_VIEWS as readonly string[]).includes(view);
}

/** What a request on the explorer does with its search. */
export interface ExplorerSearch {
  /** A semantic search, or a search of the records like one, ranks the records. */
  ranking: boolean;
  /** The ranking search is run: not for the overview, which shows no ranking. */
  runsRanking: boolean;
  /** The text the records' own fields are searched for; none while a search ranks them. */
  fieldText: string | undefined;
}

/**
 * What a request on the explorer does with its search.
 *
 * @param q The search text.
 * @param semantic Whether the text is a semantic search's.
 * @param similarTo The record whose look-alikes are searched for; empty for none.
 * @param overviewShown Whether the overview is the view asked for.
 */
export function explorerSearch(
  q: string,
  semantic: boolean,
  similarTo: string,
  overviewShown: boolean,
): ExplorerSearch {
  const ranking = (semantic && q !== "") || similarTo !== "";
  return {
    ranking,
    runsRanking: ranking && !overviewShown,
    // The text of a search that ranks is no text to find in the records' fields.
    fieldText: ranking || q === "" ? undefined : q,
  };
}
