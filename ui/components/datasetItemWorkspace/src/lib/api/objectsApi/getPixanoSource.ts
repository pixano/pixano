/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { BaseSchema, Source, type SaveItem } from "@pixano/core";
import { get, type Writable } from "svelte/store";
import { saveData } from "../../stores/datasetItemWorkspaceStores";
import { addOrUpdateSaveItem } from "./toggleObjectDisplayControl";

export const getPixanoSource = (srcStore: Writable<Source[]>): Source => {
  //manage source: add if we need it
  //TMP (TODO) - currently, all add/update from Pixano App are under a same unique source
  const sources = get<Source[]>(srcStore);
  let pixanoSource = sources.find((src) => src.data.name === "Pixano" && src.data.kind === "other");
  if (!pixanoSource) {
    const now = new Date(Date.now()).toISOString();
    pixanoSource = new Source({
      id: "pixano_source",
      created_at: now,
      updated_at: now,
      table_info: { name: "source", group: "source", base_schema: BaseSchema.Source },
      data: { name: "Pixano", kind: "other", metadata: "{}" },
    });
    srcStore.update((sources) => {
      sources.push(pixanoSource!);
      return sources;
    });
    //save it
    const save_item: SaveItem = {
      change_type: "add",
      object: pixanoSource,
    };
    saveData.update((current_sd) => addOrUpdateSaveItem(current_sd, save_item));
  }
  return pixanoSource;
};
