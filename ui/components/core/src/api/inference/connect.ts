/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

export async function inferenceConnect(url: string): Promise<void> {
  return new Promise((resolve, reject) => {
    fetch(`/inference/connect?url=${encodeURIComponent(url)}`, {
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      method: "POST",
    })
      .then(async (response) => {
        if (response.ok) {
          resolve();
        } else {
          const err = await response.text();
          console.log("api.inferenceConnect -", response.status, response.statusText, err);
          reject(err);
        }
      })
      .catch((err) => {
        console.log("api.inferenceConnect -", err);
        reject(err);
      });
  });
}
