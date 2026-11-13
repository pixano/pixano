/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { PageLoad } from "./$types";
import { browser } from "$app/environment";
import { listRecords, searchRecords } from "$lib/api";
import { serverDetail } from "$lib/api/apiClient";
import { getOverview, type DatasetOverview, type OverviewRequest } from "$lib/api/overviewApi";
import {
  DEFAULT_DATASET_GRID_SIZE,
  DEFAULT_DATASET_TABLE_PAGE,
  DEFAULT_DATASET_TABLE_SIZE,
} from "$lib/constants";
import type { DatasetBrowser } from "$lib/types/dataset";
import { isHeld, orderedSpaces } from "$lib/utils/embeddingSpaces";
import { explorerSearch, isExplorerView, type ExplorerView } from "$lib/utils/explorerSearch";
import { getRouteSearchParams } from "$lib/utils/routes";

const SEMANTIC_LIMIT = 100;

/** Extract the backend's actionable `detail` from a failed search, with an honest fallback. */
function searchErrorMessage(error: unknown): string {
  const detail = serverDetail(error);
  return detail
    ? `Semantic search failed — showing the unranked list. ${detail}`
    : "Semantic search failed — showing the unranked list.";
}

/** The view the URL, or else the dataset's remembered one, asks for; none before the data decides. */
function requestedView(datasetId: string, urlView: string | null): ExplorerView | null {
  if (isExplorerView(urlView)) return urlView;
  if (!browser) return null;
  const stored = localStorage.getItem(`pixano.explorer.view.${datasetId}`);
  return isExplorerView(stored) ? stored : null;
}

/** The overview of the records the filters keep, or why it could not be read. */
async function readOverview(
  datasetId: string,
  request: OverviewRequest,
): Promise<{ overview: DatasetOverview | null; overviewError: string }> {
  try {
    return { overview: await getOverview(datasetId, request), overviewError: "" };
  } catch (error) {
    return {
      overview: null,
      overviewError: serverDetail(error) ?? "The overview could not be read.",
    };
  }
}

/** View precedence: URL param → per-dataset localStorage → data-driven default. */
function resolveView(
  datasetId: string,
  urlView: string | null,
  browserData: DatasetBrowser,
): ExplorerView {
  const requested = requestedView(datasetId, urlView);
  if (requested !== null) return requested;
  // One unified rule, no workspace branching: grid whenever records carry previews.
  const hasPreviews = (browserData.card_data ?? []).some((card) => card.previews.length > 0);
  return hasPreviews ? "grid" : "table";
}

export const load: PageLoad = async ({ params, url, parent }) => {
  const searchParams = getRouteSearchParams(url);
  const urlView = searchParams.get("view");
  const currentPage = parseInt(searchParams.get("page") ?? String(DEFAULT_DATASET_TABLE_PAGE));
  const defaultSize = urlView === "table" ? DEFAULT_DATASET_TABLE_SIZE : DEFAULT_DATASET_GRID_SIZE;
  const size = parseInt(searchParams.get("size") ?? String(defaultSize));
  const sort = searchParams.get("sort") ?? "";
  const order = searchParams.get("order") ?? "asc";
  const filters = searchParams.getAll("filter").filter((value) => value !== "");
  const q = searchParams.get("q") ?? "";
  const where = searchParams.get("where") ?? "";
  const semantic = searchParams.get("semantic") === "1";
  const similarTo = searchParams.get("similar_to") ?? "";
  // The model a search reads, by its id: the default one when the URL names none. Kept while no
  // search runs, for the next one. One the dataset does not hold is left for the default, and said:
  // a search naming it would only fail.
  const named = searchParams.get("model") ?? "";
  const held = named === "" || isHeld(orderedSpaces((await parent()).filterSchema?.search), named);
  const model = held ? named : "";
  const searchNotice = held
    ? ""
    : `This dataset holds no embeddings of model '${named}': a search reads its default model.`;
  // The overview of the records the filters keep, read beside them when it is the view asked for. A
  // semantic search ranks the records: the overview counts them all, reads no text of it, and the
  // search is not run for a view that shows no ranking.
  const bySplit = searchParams.get("by_split") === "1";
  const overviewShown = requestedView(params.datasetId, urlView) === "overview";
  const search = explorerSearch(q, semantic, similarTo, overviewShown);
  const overviewRead = overviewShown
    ? readOverview(params.datasetId, {
        filters,
        q: search.fieldText,
        where: where || undefined,
        bySplit,
      })
    : Promise.resolve({ overview: null, overviewError: "" });

  // Semantic search is a separate ranked endpoint (not paginated); a text query or a
  // find-similar target activates it. Structured filter chips apply as a prefilter.
  if (search.runsRanking) {
    try {
      const browserData = await searchRecords(params.datasetId, {
        model: model || undefined,
        text: similarTo ? undefined : q,
        similarTo: similarTo || undefined,
        k: SEMANTIC_LIMIT,
        filters,
        where: where || undefined,
      });
      return {
        browserData,
        pagination: { currentPage: 1, size: SEMANTIC_LIMIT, sort, order, filters, q, where },
        semantic: { active: true, similarTo, model },
        searchError: "",
        searchNotice,
        ...(await overviewRead),
        bySplit,
        view: resolveView(params.datasetId, urlView, browserData),
      };
    } catch (error) {
      // A failed semantic search (broken embeddings, unreachable provider…) degrades to the
      // regular listing with the backend's actionable detail in an inline banner instead of
      // the route error page.
      const browserData = await listRecords(params.datasetId, {
        offset: 0,
        limit: size,
        filters,
        where: where || undefined,
        order,
      });
      return {
        browserData,
        pagination: { currentPage: 1, size, sort: "", order, filters, q, where },
        semantic: { active: false, similarTo: "", model },
        searchError: searchErrorMessage(error),
        searchNotice,
        ...(await overviewRead),
        bySplit,
        view: resolveView(params.datasetId, urlView, browserData),
      };
    }
  }

  const browserData = await listRecords(params.datasetId, {
    offset: (currentPage - 1) * size,
    limit: size,
    filters,
    q: search.fieldText,
    where: where || undefined,
    sort: sort || undefined,
    order,
  });

  return {
    browserData,
    pagination: { currentPage, size, sort, order, filters, q, where },
    // Kept for the overview's notice, and for the views the search ranks once one is back.
    semantic: { active: search.ranking, similarTo, model },
    searchError: "",
    searchNotice,
    ...(await overviewRead),
    bySplit,
    view: resolveView(params.datasetId, urlView, browserData),
  };
};
