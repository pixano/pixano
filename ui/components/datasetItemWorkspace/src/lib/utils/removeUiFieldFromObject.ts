/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

export const removeFieldFromObject = <T extends Record<string, any>, K extends keyof T>(
  object: T,
  field: K,
): Omit<T, K> => {
  if (!(field in object)) {
    return object;
  }
  const { [field]: _, ...rest } = object;

  return rest;
};
