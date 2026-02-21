/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { initDisplayControl, type Annotation, type DisplayControl } from "$lib/types/dataset";

export const toggleAnnotationDisplayControl = (
  object: Annotation,
  displayControlProperty: keyof DisplayControl,
  value: boolean,
): Annotation => {
  const currentDisplayControl = {
    ...initDisplayControl,
    ...(object.ui.displayControl || {}),
  } as DisplayControl;
  if (currentDisplayControl[displayControlProperty] === value) return object;
  object.ui.displayControl = {
    ...currentDisplayControl,
    [displayControlProperty]: value,
  } as DisplayControl;
  return object;
};
