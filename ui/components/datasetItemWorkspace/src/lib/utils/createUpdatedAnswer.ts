/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { Message } from "@pixano/core";

export const createUpdatedAnswer = ({
  prevAnswer,
  content,
}: {
  prevAnswer: Message;
  content: string;
}) => {
  /* eslint-disable @typescript-eslint/no-unused-vars */
  const { ui, ...rest } = prevAnswer;

  // Mandatory for storybook not to crash
  if ("_constructor-name_" in rest) {
    delete rest["_constructor-name_"];
  }

  return new Message({
    ...rest,
    data: {
      ...rest.data,
      content,
    },
  });
};
