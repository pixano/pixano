/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

/* eslint-disable-next-line @typescript-eslint/no-explicit-any */
export const removeFieldFromValue = <T extends Record<string, any>, K extends keyof T>(
  value: T,
  field: K,
): Omit<T, K> => {
  if (!(field in value)) {
    return value;
  }
  /* eslint-disable-next-line @typescript-eslint/no-unused-vars */
  const { [field]: _, ...rest } = value;

  return rest;
};
