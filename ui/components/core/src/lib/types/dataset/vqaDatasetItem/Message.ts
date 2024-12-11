/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { z } from "zod";

export enum MessageType {
  SYSTEM = "SYSTEM",
  QUESTION = "QUESTION",
  ANSWER = "ANSWER",
}

export const messageSchema = z.object({
  number: z.number(),
  user: z.string(),
  type: z.nativeEnum(MessageType),
  content: z.string(),
  timestamp: z.string().optional(),
});

export class Message {
  number: number;
  user: string;
  type: MessageType;
  content: string;
  timestamp: string;

  constructor(message: z.infer<typeof messageSchema>) {
    const parsedMessage = messageSchema.safeParse(message);
    if (!parsedMessage.success) {
      throw new Error("Invalid message object");
    }

    this.number = parsedMessage.data.number;
    this.user = parsedMessage.data.user;
    this.type = parsedMessage.data.type;
    this.content = parsedMessage.data.content;
    this.timestamp = parsedMessage.data.timestamp ?? new Date().toISOString();
  }

  static deepCreateInstanceArray(
    objs: Record<string, z.infer<typeof messageSchema>[]>,
  ): Record<string, Message[]> {
    const newObj: Record<string, Message[]> = {};
    for (const [k, vs] of Object.entries(objs)) {
      newObj[k] = [];
      for (const v of vs) {
        const message = new Message(v);
        newObj[k].push(message);
      }
    }
    return newObj;
  }
}
