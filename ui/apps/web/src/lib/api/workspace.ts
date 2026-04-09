/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { requestJson } from "./apiClient";
import type { ImageResponse, PaginatedResponse } from "./restTypes";

export async function loadImage(datasetId: string, recordId: string, imageId: string): Promise<ImageResponse> {
  return await requestJson<ImageResponse>(`/datasets/${datasetId}/records/${recordId}/images/${imageId}`, {}, "getImage");
}

export async function loadImages(datasetId: string, recordId: string): Promise<ImageResponse[]> {
  const res = await requestJson<PaginatedResponse<ImageResponse>>(`/datasets/${datasetId}/records/${recordId}/images`, {}, "loadRecordImages");
  return res.items;
}
