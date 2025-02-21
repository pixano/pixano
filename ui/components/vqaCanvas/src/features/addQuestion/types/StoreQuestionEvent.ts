/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { QuestionTypeEnum } from "@pixano/core";

export type StoreQuestionEvent = {
  content: string;
  question_type: QuestionTypeEnum;
  choices: string[];
};
