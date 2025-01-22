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

export const messageSchema = z
  .object({
    number: z.number(),
    user: z.string(),
    type: z.nativeEnum(MessageTypeEnum),
    content: z.string(),
    timestamp: z.string(),
  })
  .passthrough();

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
    return super.nonFeaturesFields().concat(["number", "user", "type", "content", "timestamp"]);
  }
}
