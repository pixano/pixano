/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { requestJson } from "./apiClient";
import type {
  CalibratedImageResponse,
  PaginatedResponse,
  PointCloudResponse,
  TextResponse,
} from "./restTypes";

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

export async function loadTextByLogicalName(
  datasetId: string,
  recordId: string,
  logicalName: string,
): Promise<TextResponse | null> {
  const res = await requestJson<PaginatedResponse<TextResponse>>(
    `/datasets/${datasetId}/records/${recordId}/texts?view_name=${encodeURIComponent(logicalName)}`,
    {},
    "loadTextByLogicalName",
  );
  return res.items[0] ?? null;
}
