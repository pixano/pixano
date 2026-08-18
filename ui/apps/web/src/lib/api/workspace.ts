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

/**
 * Every image view of a record, in one round-trip.
 *
 * `loadImageByLogicalName` answers "this widget's image"; this answers "every
 * camera that saw this record", which is what a consumer needs when it works
 * across views rather than within one — projecting the point cloud onto the
 * cameras, for instance. Asking per name instead would cost one request per
 * camera and still not say how many there are.
 */
export async function listRecordImages(
  datasetId: string,
  recordId: string,
): Promise<CalibratedImageResponse[]> {
  const res = await requestJson<PaginatedResponse<CalibratedImageResponse>>(
    `/datasets/${datasetId}/records/${recordId}/images`,
    {},
    "listRecordImages",
  );
  return res.items;
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
