/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { Message } from "@pixano/core";

export const groupMessagesByNumber = (array: Message[]) => {
  const groups = array.reduce(
    (acc, item) => {
      const groupKey = item.data.number;
      return {
        ...acc,
        [groupKey]: [...(acc[groupKey] || []), item],
      };
    },
    {} as { [key: string]: Message[] },
  );

  return Object.entries(groups)
    .sort((a, b) => +a[0] - +b[0])
    .map(([, value]) => value);
};
