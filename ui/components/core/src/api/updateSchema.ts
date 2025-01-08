/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { Schema } from "../lib/types";

export async function updateSchema(route: string, ds_id: string, sch: Schema, no_table: boolean) {
  const url = no_table
    ? `/${route}/${ds_id}/${sch.id}`
    : `/${route}/${ds_id}/${sch.table_info.name}/${sch.id}`;
  try {
    const response = await fetch(url, {
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      method: "PUT",
      body: JSON.stringify(sch),
    });
    if (!response.ok) {
      console.log(
        "api.updateSchema -",
        response.status,
        response.statusText,
        await response.text(),
      );
    }
  } catch (e) {
    console.log("api.updateSchema -", e);
  }
}
