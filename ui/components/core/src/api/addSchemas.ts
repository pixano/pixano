/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { Schema } from "../lib/types";

export async function addSchemas(
  route: string,
  ds_id: string,
  schs: Schema[],
  table: string,
  no_table: boolean,
) {
  const url = no_table ? `/${route}/${ds_id}/` : `/${route}/${ds_id}/${table}/`;
  try {
    const response = await fetch(url, {
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      method: "POST",
      body: JSON.stringify(schs),
    });
    if (!response.ok) {
      console.log("api.addSchemas -", response.status, response.statusText, await response.text());
    }
  } catch (e) {
    console.log("api.addSchemas -", e);
  }
}
