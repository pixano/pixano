/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { PageLoad } from "./$types";
import { listRecords } from "$lib/api";
import { DEFAULT_DATASET_TABLE_PAGE, DEFAULT_DATASET_TABLE_SIZE } from "$lib/constants";
import { getRouteSearchParams } from "$lib/utils/routes";

export const load: PageLoad = async ({ params, url, parent }) => {
  const { dataset } = await parent();
  const searchParams = getRouteSearchParams(url);
  const currentPage = parseInt(searchParams.get("page") ?? String(DEFAULT_DATASET_TABLE_PAGE));
  const size = parseInt(searchParams.get("size") ?? String(DEFAULT_DATASET_TABLE_SIZE));
  const sortCol = searchParams.get("sort") ?? "";
  const sortOrder = searchParams.get("order") ?? "asc";
  const where = searchParams.get("filter") ?? "";

  const sort = sortCol ? { col: sortCol, order: sortOrder } : { col: "created_at", order: "asc" };

  const browserData = await listRecords(params.datasetId, {
    offset: (currentPage - 1) * size,
    limit: size,
    where: where || undefined,
    sort,
    workspaceType: dataset.workspace,
  });

  return {
    browserData,
    pagination: { currentPage, size, sort, where },
  };
};
