/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { Message } from "@pixano/core";

export const createUpdatedMessage = ({
  message,
  newMessageContent,
}: {
  message: Message;
  newMessageContent: string;
}) => {
  /* eslint-disable @typescript-eslint/no-unused-vars */
  const { ui, ...rest } = message;
  return new Message({
    ...rest,
    data: {
      ...message.data,
      content: newMessageContent,
    },
  });
};
