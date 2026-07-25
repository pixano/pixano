/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { PageLoad } from "./$types";
import { listRecords } from "$lib/api";
import { DEFAULT_DATASET_TABLE_PAGE, DEFAULT_DATASET_TABLE_SIZE } from "$lib/constants";
import { getRouteSearchParams } from "$lib/utils/routes";

export const load: PageLoad = async ({ params, url }) => {
  const searchParams = getRouteSearchParams(url);
  const currentPage = parseInt(searchParams.get("page") ?? String(DEFAULT_DATASET_TABLE_PAGE));
  const size = parseInt(searchParams.get("size") ?? String(DEFAULT_DATASET_TABLE_SIZE));
  const sort = searchParams.get("sort") ?? "";
  const order = searchParams.get("order") ?? "asc";
  const filters = searchParams.getAll("filter").filter((value) => value !== "");
  const q = searchParams.get("q") ?? "";
  const where = searchParams.get("where") ?? "";

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
  };
};
