/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { MultimodalImageNLPTask, type ModelList } from "../../lib/types";

export async function listModels(task: MultimodalImageNLPTask | null = null): Promise<ModelList[]> {
  const url =
    task === null
      ? "/inference/models/list"
      : `/inference/models/list?task=${encodeURIComponent(task)}`;

  try {
    const response = await fetch(url, {
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      method: "GET",
    });

    if (!response.ok) {
      console.log("api.listModels -", response.status, response.statusText, await response.text());
      return [];
    }

    return (await response.json()) as ModelList[];
  } catch (e) {
    console.log("api.listModels -", e);
    return [];
  }
}
