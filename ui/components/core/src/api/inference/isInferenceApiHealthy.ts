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
    });

    if (!response.ok) {
      return false;
    }

    // console.log("api.inferenceConnect -", response.status, response.statusText);
    return true;
  } catch {
    return false;
  }
}
