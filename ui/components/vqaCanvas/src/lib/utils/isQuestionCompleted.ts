/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { Message } from "@pixano/core";
import { MessageTypeEnum } from "@pixano/core";

const EMPTY_CONTENT_STRING = ["", "[[]]"];

export const isQuestionCompleted = (messages: Message[]) => {
  const answers = messages.filter((m) => m.data.type === MessageTypeEnum.ANSWER);
  return answers.every((a) => !EMPTY_CONTENT_STRING.includes(a.data.content.trim()));
};
