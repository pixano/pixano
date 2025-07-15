/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

export async function isInferenceApiHealthy(url: string): Promise<boolean> {
  try {
    const response = await fetch(`/inference/connect?url=${encodeURIComponent(url)}`, {
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      method: "POST",
      signal: AbortSignal.timeout(4000),
    });

    if (!response.ok) {
      // console.log("api.inferenceConnect -", response.status, response.statusText);
      return false;
    }
    return true;
  } catch {
    return false;
  }
}
