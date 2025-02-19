import type { QuestionTypeEnum } from "@pixano/core";

export type StoreQuestionEvent = {
  content: string;
  question_type: QuestionTypeEnum;
  choices: string[];
};
