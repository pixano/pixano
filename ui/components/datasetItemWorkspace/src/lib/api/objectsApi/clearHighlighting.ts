/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { annotations, newShape } from "../../stores/datasetItemWorkspaceStores";

export const clearHighlighting = () => {
  //deselect everything = unhighlight all and stop editing
  newShape.set({ status: "none" });
  annotations.update((anns) =>
    anns.map((ann) => {
      ann.ui.displayControl = { ...ann.ui.displayControl, editing: false, highlighted: "all" };
      return ann;
    }),
  );
};
