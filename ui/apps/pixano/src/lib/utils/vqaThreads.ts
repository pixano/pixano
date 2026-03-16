/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { MessageTypeEnum, type Message } from "$lib/types/dataset";
import type { QuestionThread } from "$lib/types/vqa";

function getConversationId(message: Message): string {
  return typeof message.data.conversation_id === "string" && message.data.conversation_id.length > 0
    ? message.data.conversation_id
    : "__default__";
}

function sortMessages(left: Message, right: Message): number {
  return (left.data.number ?? 0) - (right.data.number ?? 0);
}

export function buildQuestionThreads(messages: Message[]): QuestionThread[] {
  const byConversation = new Map<string, Message[]>();

  for (const message of messages) {
    const conversationId = getConversationId(message);
    const bucket = byConversation.get(conversationId);
    if (bucket) bucket.push(message);
    else byConversation.set(conversationId, [message]);
  }

  const threads: QuestionThread[] = [];

  for (const [conversationId, conversationMessages] of byConversation.entries()) {
    const ordered = [...conversationMessages].sort(sortMessages);
    let currentThread: QuestionThread | null = null;

    for (const message of ordered) {
      if (message.data.type === MessageTypeEnum.QUESTION) {
        if (currentThread) threads.push(currentThread);
        currentThread = {
          conversationId,
          question: message,
          messages: [message],
          answers: [],
        };
        continue;
      }

      if (!currentThread) {
        continue;
      }

      currentThread.messages.push(message);
      if (message.data.type === MessageTypeEnum.ANSWER) {
        currentThread.answers.push(message);
      }
    }

    if (currentThread) threads.push(currentThread);
  }

  return threads.sort((left, right) => sortMessages(left.question, right.question));
}
