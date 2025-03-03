/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

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
