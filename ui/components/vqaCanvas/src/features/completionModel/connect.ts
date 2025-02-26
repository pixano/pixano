/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { api } from "@pixano/core";

export async function connect(url: string): Promise<boolean> {
  try {
    await api.inferenceConnect(url);
    console.log("connected to Pixano Inference at:", url);
    return true;
  } catch (err) {
    console.error("NOT connected to Pixano Inference!");
    return false;
  }
}
