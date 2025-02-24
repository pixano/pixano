/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { type ModelList } from "../../lib/types";

export async function listModels(task: string | null = null): Promise<ModelList[]> {
  let model_list: ModelList[] = [];
  let url = "/inference/models/list";
  if (task) url += "?task=" + encodeURIComponent(task);
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
    } else {
      model_list = await response.json() as ModelList[];
    }
  } catch (e) {
    console.log("api.listModels -", e);
  }
  return model_list;
}
