/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { requestJson } from "./apiClient";
import type { CalibratedImageResponse, PaginatedResponse, PointCloudResponse } from "./restTypes";

export async function loadImageByLogicalName(
  datasetId: string,
  recordId: string,
  logicalName: string,
): Promise<CalibratedImageResponse | null> {
  const res = await requestJson<PaginatedResponse<CalibratedImageResponse>>(
    `/datasets/${datasetId}/records/${recordId}/images?view_name=${encodeURIComponent(logicalName)}`,
    {},
    "loadImageByLogicalName",
  );
  return res.items[0] ?? null;
}

export async function loadPointCloudByLogicalName(
  datasetId: string,
  recordId: string,
  logicalName: string,
): Promise<PointCloudResponse | null> {
  const res = await requestJson<PaginatedResponse<PointCloudResponse>>(
    `/datasets/${datasetId}/records/${recordId}/point-clouds?view_name=${encodeURIComponent(logicalName)}`,
    {},
    "loadPointCloudByLogicalName",
  );
  return res.items[0] ?? null;
}
