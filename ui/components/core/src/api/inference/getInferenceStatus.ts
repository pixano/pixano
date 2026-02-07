/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

export interface ConnectedProvider {
  name: string;
  url: string | null;
}

export interface InferenceStatusResponse {
  connected: boolean;
  providers: ConnectedProvider[];
  default: string | null;
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
      return { connected: false, providers: [], default: null };
    }

    return (await response.json()) as InferenceStatusResponse;
  } catch {
    return { connected: false, providers: [], default: null };
  }
}
