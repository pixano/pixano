/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

// Imports
import type { DatasetItem, Annotation, Entity } from "../types/datasetTypes";

export function getView(item: DatasetItem, obj: Annotation | Entity): View {
    return item.views[obj.data.view_ref.name].find((view) => view.id === obj.data.view_ref.id);
  }
