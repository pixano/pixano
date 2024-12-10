/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { Annotation, DisplayControl } from "@pixano/core";

export const toggleObjectDisplayControl = (
  object: Annotation,
  displayControlProperty: keyof DisplayControl,
  value: boolean,
): Annotation => {
  object.ui.displayControl = {
    ...(object.ui.displayControl || {}),
    [displayControlProperty]: value,
  };
  return object;
};
