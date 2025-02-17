/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

export enum ContentChangeEventType {
  UPDATE = "UPDATE",
  NEW_ANSWER = "NEW_ANSWER",
}

export type ContentChangeEvent = UpdatedMessageEvent | NewAnswerEvent;

export interface UpdatedMessageEvent {
  type: ContentChangeEventType.UPDATE;
  answerId: string;
  content: string;
}

export interface NewAnswerEvent {
  type: ContentChangeEventType.NEW_ANSWER;
  questionId: string;
  content: string;
}

export const isNewAnswerEvent = (
  event: CustomEvent<ContentChangeEvent>,
): event is CustomEvent<NewAnswerEvent> => event.detail.type === ContentChangeEventType.NEW_ANSWER;

export const isUpdatedMessageEvent = (
  event: CustomEvent<ContentChangeEvent>,
): event is CustomEvent<UpdatedMessageEvent> => event.detail.type === ContentChangeEventType.UPDATE;
