/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { Message } from "@pixano/core";

export const createUpdatedMessage = ({
  message,
  newContent,
  newChoices,
  explanation,
}: {
  message: Message;
  newContent: string;
  newChoices?: string[];
  explanation?: string;
}) => {
  /* eslint-disable @typescript-eslint/no-unused-vars */
  const { ui, ...rest } = message;

  // Mandatory for storybook not to crash
  if ("_constructor-name_" in rest) {
    delete rest["_constructor-name_"];
  }

  return new Message({
    ...rest,
    data: {
      ...rest.data,
      content: newContent,
      ...(newChoices !== undefined && { answers: newChoices }),
      ...(explanation !== undefined && { explanations: [explanation] }),
    },
  });
};
