/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

export type DatasetStats = Record<string, Record<string, number>>;

export async function getDatasetStats(
  datasetId: string,
  options?: { signal?: AbortSignal },
): Promise<DatasetStats> {
  try {
    const response = await fetch(`/datasets/${datasetId}/stats`, {
      method: "GET",
      signal: options?.signal,
    });
    if (response.ok) {
      return (await response.json()) as DatasetStats;
    }
    console.log(
      "api.getDatasetStats -",
      response.status,
      response.statusText,
      await response.text(),
    );
  } catch (e) {
    if (!(typeof e === "string" && e === "aborted")) console.log("api.getDatasetStats -", e);
  }
  return {};
}
