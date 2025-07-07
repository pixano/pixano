/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

export async function getModels(): Promise<Array<string>> {
  let models: Array<string> | undefined;

  try {
    const response = await fetch("/models/");
    if (response.ok) {
      models = (await response.json()) as Array<string>;
    } else {
      models = [];
      console.log("api.getModels -", response.status, response.statusText); //, await response.text());  <-- not very informative
    }
  } catch (e) {
    models = [];
    console.log("api.getModels -", e);
  }

  return models;
}
