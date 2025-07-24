/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { splitWithLimit } from "../utils";

export async function deleteSchemasByIds(
  route: string,
  ds_id: string,
  sch_ids: string[],
  table_name: string,
  no_table: boolean,
) {
  const base_url = no_table ? `/${route}/${ds_id}?ids=` : `/${route}/${ds_id}/${table_name}?ids=`;
  //split sch_ids to avoid "431 Request Header Fields Too Large" if too long
  const url_chunks = splitWithLimit(sch_ids, "&ids=", 8000);
  //const results =
  await Promise.all(
    url_chunks.map(async (ids_query) => {
      const url = base_url + ids_query;
      try {
        const response = await fetch(url, {
          method: "DELETE",
        });
        if (!response.ok) {
          console.log(
            "api.deleteSchema -",
            response.status,
            response.statusText,
            await response.text(),
          );
        }
      } catch (e) {
        console.log("api.deleteSchema -", e);
      }
    }),
  );
  //return results.flat();
}
