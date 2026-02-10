/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { QuestionTypeEnum } from "@pixano/core";

export type LabelFormat = "numeric" | "alpha_lower" | "alpha_upper" | "none";

export type StoreQuestionEvent = {
  content: string;
  question_type: QuestionTypeEnum;
  choices: string[];
  labelFormat?: LabelFormat;
};
