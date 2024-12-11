/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { z } from "zod";
import { DatasetItem, datasetItemSchema } from "../DatasetItem";
import { Conversation, conversationSchema } from "./Conversation";
import { Message, messageSchema } from "./Message";

const vqaDatasetItemSchema = datasetItemSchema.extend({
  conversations: z.record(z.string(), z.array(conversationSchema)),
  messages: z.record(z.string(), z.array(messageSchema)),
});

export type VqaDatasetItemType = z.infer<typeof vqaDatasetItemSchema>;

export class VqaDatasetItem extends DatasetItem implements VqaDatasetItemType {
  conversations: Record<string, Conversation[]>;
  messages: Record<string, Message[]>;

  //UI only fields
  ui: {
    datasetId: string;
    type: string;
  } = { datasetId: "", type: "" };

  constructor(obj: VqaDatasetItemType) {
    vqaDatasetItemSchema.parse(obj);
    super(obj);

    this.conversations = Conversation.deepCreateInstanceArray(obj.conversations);
    this.messages = Message.deepCreateInstanceArray(obj.messages);
  }
}
