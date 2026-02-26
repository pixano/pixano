/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { PageLoad } from "./$types";
import { getBrowser } from "$lib/api";
import {
  DEFAULT_DATASET_TABLE_PAGE,
  DEFAULT_DATASET_TABLE_SIZE,
} from "$lib/constants";

export const load: PageLoad = async ({ params, url }) => {
  const currentPage = parseInt(
    url.searchParams.get("page") ?? String(DEFAULT_DATASET_TABLE_PAGE),
  );
  const size = parseInt(
    url.searchParams.get("size") ?? String(DEFAULT_DATASET_TABLE_SIZE),
  );
  const sortCol = url.searchParams.get("sort") ?? "";
  const sortOrder = url.searchParams.get("order") ?? "asc";
  const querySearch = url.searchParams.get("q") ?? "";
  const queryModel = url.searchParams.get("model") ?? "";
  const where = url.searchParams.get("filter") ?? "";

  const sort =
    sortCol ? { col: sortCol, order: sortOrder } : { col: "created_at", order: "asc" };
  const query =
    querySearch && queryModel ? { model: queryModel, search: querySearch } : undefined;

  const browserData = await getBrowser(
    params.datasetId,
    currentPage,
    size,
    query,
    where || undefined,
    sort,
  );

  return {
    browserData,
    pagination: { currentPage, size, sort, query, where },
  };
};
