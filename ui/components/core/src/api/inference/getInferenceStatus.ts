/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

export interface InferenceStatusResponse {
  connected: boolean;
  url: string | null;
}

export async function getInferenceStatus(): Promise<InferenceStatusResponse> {
  try {
    const response = await fetch("/inference/status", {
      headers: {
        Accept: "application/json",
      },
      method: "GET",
    });

    if (!response.ok) {
      return { connected: false, url: null };
    }

    return (await response.json()) as InferenceStatusResponse;
  } catch {
    return { connected: false, url: null };
  }
}
