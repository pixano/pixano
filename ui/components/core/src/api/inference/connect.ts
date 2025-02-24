/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

export async function inferenceConnect(url: string) {
  //TODO? check url is an actual url
  try {
    const response = await fetch(`/inference/connect?url=${encodeURIComponent(url)}`, {
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      method: "POST",
    });
    if (!response.ok) {
      console.log(
        "api.inferenceConnect -",
        response.status,
        response.statusText,
        await response.text(),
      );
    }
  } catch (e) {
    console.log("api.inferenceConnect -", e);
  }
}
