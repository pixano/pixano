/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

/* eslint-disable-next-line @typescript-eslint/no-explicit-any */
export const removeFieldFromObject = <T extends Record<string, any>, K extends keyof T>(
  object: T,
  field: K,
): Omit<T, K> => {
  if (!(field in object)) {
    return object;
  }
  /* eslint-disable-next-line @typescript-eslint/no-unused-vars */
  const { [field]: _, ...rest } = object;

  return rest;
};
