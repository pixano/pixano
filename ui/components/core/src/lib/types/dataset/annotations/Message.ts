/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { z } from "zod";

import { Annotation, type AnnotationType, type AnnotationUIFields } from ".";
import { BaseSchema } from "../BaseSchema";
import type { BaseDataFields } from "../datasetTypes";
import { WorkspaceType } from "../workspaceType";

export enum MessageTypeEnum {
  SYSTEM = "SYSTEM",
  QUESTION = "QUESTION",
  ANSWER = "ANSWER",
}

export enum QuestionTypeEnum {
  OPEN = "OPEN",
  SINGLE_CHOICE = "SINGLE_CHOICE",
  SINGLE_CHOICE_EXPLANATION = "SINGLE_CHOICE_EXPLANATION",
  MULTI_CHOICE = "MULTI_CHOICE",
  MULTI_CHOICE_EXPLANATION = "MULTI_CHOICE_EXPLANATION",
}

const baseMessageSchema = z
  .object({
    number: z.number(),
    user: z.string(),
    timestamp: z.string(),
    content: z.string(),
  })
  .passthrough();

const questionSchema = baseMessageSchema.extend({
  type: z.literal(MessageTypeEnum.QUESTION),
  choices: z.string().array(),
  question_type: z.nativeEnum(QuestionTypeEnum),
});

const answerSchema = baseMessageSchema.extend({
  type: z.literal(MessageTypeEnum.ANSWER),
});

const systemSchema = baseMessageSchema.extend({
  type: z.literal(MessageTypeEnum.SYSTEM),
});

export const messageSchema = z.discriminatedUnion("type", [
  questionSchema,
  answerSchema,
  systemSchema,
]);

export type QuestionType = z.infer<typeof questionSchema>;
export type AnswerType = z.infer<typeof answerSchema>;
export type SystemMessageType = z.infer<typeof systemSchema>;
export type MessageType = z.infer<typeof messageSchema>;

export class Message extends Annotation {
  declare data: MessageType & AnnotationType;

  //UI only fields
  ui: AnnotationUIFields = { datasetItemType: WorkspaceType.IMAGE_VQA };

  constructor(obj: BaseDataFields<MessageType>) {
    if (obj.table_info.base_schema !== BaseSchema.Message) throw new Error("Not a Message");
    messageSchema.parse(obj.data);
    super(obj as unknown as BaseDataFields<AnnotationType>);
    this.data = obj.data as MessageType & AnnotationType;
  }

  static nonFeaturesFields(): string[] {
    return super
      .nonFeaturesFields()
      .concat([
        "number",
        "user",
        "type",
        "content",
        "timestamp",
        "choices",
        "question_type",
        "explanation",
      ]);
  }
}

export const isQuestionData = (messageType: MessageType): messageType is QuestionType => {
  return messageType.type === MessageTypeEnum.QUESTION;
};
