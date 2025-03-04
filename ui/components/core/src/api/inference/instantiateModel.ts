/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { type ModelConfig } from "../../lib/types";

export async function instantiateModel(model_config: ModelConfig): Promise<boolean> {
  try {
    const response = await fetch(`/inference/models/instantiate`, {
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      method: "POST",
      body: JSON.stringify(model_config),
    });

    if (!response.ok) {
      console.log("api.instantiateModel -", response.status, response.statusText);
      return false;
    }

    return true;
  } catch (e) {
    console.log("api.instantiateModel -", e);
    return false;
  }
}
