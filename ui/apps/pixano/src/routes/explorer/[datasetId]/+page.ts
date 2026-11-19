/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { PageLoad } from "./$types";
import { browser } from "$app/environment";
import { listRecords, searchRecords } from "$lib/api";
import { serverDetail } from "$lib/api/apiClient";
import {
  DEFAULT_DATASET_GRID_SIZE,
  DEFAULT_DATASET_TABLE_PAGE,
  DEFAULT_DATASET_TABLE_SIZE,
} from "$lib/constants";
import type { DatasetBrowser } from "$lib/types/dataset";
import { isHeld, orderedSpaces } from "$lib/utils/embeddingSpaces";
import { getRouteSearchParams } from "$lib/utils/routes";

const SEMANTIC_LIMIT = 100;

type ExplorerView = "grid" | "table";

/** Extract the backend's actionable `detail` from a failed search, with an honest fallback. */
function searchErrorMessage(error: unknown): string {
  const detail = serverDetail(error);
  return detail
    ? `Semantic search failed — showing the unranked list. ${detail}`
    : "Semantic search failed — showing the unranked list.";
}

/** View precedence: URL param → per-dataset localStorage → data-driven default. */
function resolveView(
  datasetId: string,
  urlView: string | null,
  browserData: DatasetBrowser,
): ExplorerView {
  if (urlView === "grid" || urlView === "table") return urlView;
  if (browser) {
    const stored = localStorage.getItem(`pixano.explorer.view.${datasetId}`);
    if (stored === "grid" || stored === "table") return stored;
  }
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

  // Semantic search is a separate ranked endpoint (not paginated); a text query or a
  // find-similar target activates it. Structured filter chips apply as a prefilter.
  if ((semantic && q) || similarTo) {
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
        view: resolveView(params.datasetId, urlView, browserData),
      };
    }
  }

  const browserData = await listRecords(params.datasetId, {
    offset: (currentPage - 1) * size,
    limit: size,
    filters,
    q: q || undefined,
    where: where || undefined,
    sort: sort || undefined,
    order,
  });

  return {
    browserData,
    pagination: { currentPage, size, sort, order, filters, q, where },
    semantic: { active: false, similarTo: "", model },
    searchError: "",
    searchNotice,
    view: resolveView(params.datasetId, urlView, browserData),
  };
};
