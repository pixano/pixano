/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { Task } from "../../lib/types";

export interface ModelWithProvider {
  name: string;
  task: Task;
  provider_name: string;
}

export async function listAllModels(task: Task | null = null): Promise<ModelWithProvider[]> {
  const url =
    task === null
      ? "/inference/models/list-all"
      : `/inference/models/list-all?task=${encodeURIComponent(task)}`;

  try {
    const response = await fetch(url, {
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      method: "GET",
    });

    if (!response.ok) {
      console.log(
        "api.listAllModels -",
        response.status,
        response.statusText,
        await response.text(),
      );
      return [];
    }

    return (await response.json()) as ModelWithProvider[];
  } catch (e) {
    console.log("api.listAllModels -", e);
    return [];
  }
}
