/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { MessageTypeEnum, type Message } from "$lib/types/dataset";

const EMPTY_CONTENT_STRING = ["", "[[]]"];

export const isQuestionCompleted = (messages: Message[]) => {
  const answers = messages.filter((m) => m.data.type === MessageTypeEnum.ANSWER);
  return (
    answers.length > 0 &&
    answers.every((a) => !EMPTY_CONTENT_STRING.includes(a.data.content.trim()))
  );
};
