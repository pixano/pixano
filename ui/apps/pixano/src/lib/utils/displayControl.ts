/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { initDisplayControl, type Annotation, type DisplayControl } from "$lib/types/dataset";

type DisplayControllable = {
  ui: {
    displayControl?: DisplayControl;
  };
};

export const updateDisplayControl = <T extends DisplayControllable>(
  object: T,
  updates: Partial<DisplayControl>,
): T => {
  if (Object.keys(updates).length === 0) return object;

  const currentDisplayControl = {
    ...initDisplayControl,
    ...(object.ui.displayControl ?? {}),
  } as DisplayControl;

  const hasChange = Object.entries(updates).some(
    ([key, value]) => currentDisplayControl[key as keyof DisplayControl] !== value,
  );
  if (!hasChange) return object;

  object.ui.displayControl = {
    ...currentDisplayControl,
    ...updates,
  } as DisplayControl;

  return object;
};

export const toggleAnnotationDisplayControl = (
  object: Annotation,
  displayControlProperty: keyof DisplayControl,
  value: boolean,
): Annotation => {
  return updateDisplayControl(object, {
    [displayControlProperty]: value,
  } as Partial<DisplayControl>);
};
