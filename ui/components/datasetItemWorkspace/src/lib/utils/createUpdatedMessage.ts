/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { Message } from "@pixano/core";

export const createUpdatedMessage = ({
  message,
  content,
  answers,
  explanations,
}: {
  message: Message;
  content: string;
  answers?: string[];
  explanations?: string[];
}) => {
  /* eslint-disable @typescript-eslint/no-unused-vars */
  const { ui, ...rest } = message;

  // Mandatory for storybook not to crash
  if ("_constructor-name_" in rest) {
    delete rest["_constructor-name_"];
  }

  return new Message({
    ...rest,
    updated_at: new Date().toISOString(),
    data: {
      ...rest.data,
      content,
      answers: answers ?? [],
      explanations: explanations ?? [],
    },
  });
};
