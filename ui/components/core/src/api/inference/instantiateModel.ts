/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { type ModelConfig } from "../../lib/types";

export async function instantiateModel(model_config: ModelConfig): Promise<void> {
  return new Promise(async (resolve, reject) => {
    const response = await fetch(`/inference/models/instantiate`, {
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      method: "POST",
      body: JSON.stringify(model_config),
    });
    if (response.ok) {
      resolve();
    } else {
      const err = await response.text();
      console.log("api.instantiateModel -", response.status, response.statusText, err);
      reject(err);
    }
  });

  // } catch (e) {
  //   console.log("api.instantiateModel -", e);
  // }
}

export async function deleteModel(model_name: string) {
  try {
    const response = await fetch(`/inference/models/delete/${model_name}`, {
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      method: "DELETE",
    });
    if (!response.ok) {
      console.log("api.deleteModel -", response.status, response.statusText, await response.text());
    }
  } catch (e) {
    console.log("api.deleteModel -", e);
  }
}
