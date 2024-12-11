/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { z } from "zod";

export const conversationSchema = z.object({
  kind: z.string(),
  with_model: z.string(),
});

export class Conversation {
  kind: string;
  with_model: string;

  constructor(conversation: z.infer<typeof conversationSchema>) {
    const parsedConversation = conversationSchema.safeParse(conversation);
    if (!parsedConversation.success) {
      throw new Error("Invalid conversation object");
    }
    this.kind = parsedConversation.data.kind;
    this.with_model = parsedConversation.data.with_model;
  }

  static deepCreateInstanceArray(
    objs: Record<string, Conversation[]>,
  ): Record<string, Conversation[]> {
    const newObj: Record<string, Conversation[]> = {};
    for (const [k, vs] of Object.entries(objs)) {
      newObj[k] = [];
      for (const v of vs) {
        const conversation = new Conversation(v);
        newObj[k].push(conversation);
      }
    }
    return newObj;
  }
}
