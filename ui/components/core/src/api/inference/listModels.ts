/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { MultimodalImageNLPTask } from "../../lib/types";

interface Model {
  name: string;
  task: MultimodalImageNLPTask;
}

export async function listModels(task: MultimodalImageNLPTask | null = null): Promise<Model[]> {
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

    return (await response.json()) as Model[];
  } catch (e) {
    console.log("api.listModels -", e);
    return [];
  }
}
