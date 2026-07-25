/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { PageLoad } from "./$types";
import { listRecords, searchRecords } from "$lib/api";
import { DEFAULT_DATASET_TABLE_PAGE, DEFAULT_DATASET_TABLE_SIZE } from "$lib/constants";
import { getRouteSearchParams } from "$lib/utils/routes";

const SEMANTIC_LIMIT = 100;

export const load: PageLoad = async ({ params, url }) => {
  const searchParams = getRouteSearchParams(url);
  const currentPage = parseInt(searchParams.get("page") ?? String(DEFAULT_DATASET_TABLE_PAGE));
  const size = parseInt(searchParams.get("size") ?? String(DEFAULT_DATASET_TABLE_SIZE));
  const sort = searchParams.get("sort") ?? "";
  const order = searchParams.get("order") ?? "asc";
  const filters = searchParams.getAll("filter").filter((value) => value !== "");
  const q = searchParams.get("q") ?? "";
  const where = searchParams.get("where") ?? "";
  const semantic = searchParams.get("semantic") === "1";
  const similarTo = searchParams.get("similar_to") ?? "";
  const model = searchParams.get("model") ?? "";

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
      };
    } catch {
      // A failed semantic search (e.g. unreachable embedding provider) degrades to the
      // regular listing with an inline banner instead of the route error page.
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
        semantic: { active: false, similarTo: "", model: "" },
        searchError:
          "Semantic search failed — showing the unranked list. Check the inference server connection.",
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
    semantic: { active: false, similarTo: "", model: "" },
    searchError: "",
  };
};
