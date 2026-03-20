/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { Message, QuestionTypeEnum } from "$lib/types/dataset";

// --- TextCanvas types ---

export type HTMLTextSpanDataAttributes = {
  id: string;
};

// --- VQA addQuestion types ---

export type LabelFormat = "numeric" | "alpha_lower" | "alpha_upper" | "none";

export type StoreQuestionEvent = {
  content: string;
  question_type: QuestionTypeEnum;
  choices: string[];
  labelFormat?: LabelFormat;
};

// --- VQA annotateItem types ---

export enum ContentChangeEventType {
  UPDATE = "UPDATE",
  NEW_ANSWER = "NEW_ANSWER",
}

export type ContentChangeEvent = UpdatedMessageEvent | NewAnswerEvent;

export interface UpdatedMessageEvent {
  type: ContentChangeEventType.UPDATE;
  messageId: string;
  content: string;
}

export interface NewAnswerEvent {
  type: ContentChangeEventType.NEW_ANSWER;
  questionId: string;
  content: string;
}

export const isNewAnswerEvent = (event: ContentChangeEvent): event is NewAnswerEvent =>
  event.type === ContentChangeEventType.NEW_ANSWER;

export const isUpdatedMessageEvent = (event: ContentChangeEvent): event is UpdatedMessageEvent =>
  event.type === ContentChangeEventType.UPDATE;

export type DeleteQuestionEvent = { questionId: string };

export interface GenerateAnswerEvent {
  questionId: string;
  completionModel: string;
}

export interface VqaMessageContext {
  recordId: string;
  viewId: string;
  conversationId: string;
  entityIds: string[];
  imageUrl: string;
}

export interface QuestionThread {
  conversationId: string;
  question: Message;
  messages: Message[];
  answers: Message[];
}
