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
      .then((response) => {
        if (response.ok) {
          resolve();
        } else {
          console.log("api.inferenceConnect -", response.status, response.statusText);
          reject(new Error(`${response.status} ${response.statusText}`));
        }
      })
      .catch((err) => {
        console.log("api.inferenceConnect -", err);
        reject(new Error(err));
      });
  });
}
