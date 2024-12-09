import { z } from "zod";
import { BaseData, type BaseDataFields } from "../datasetTypes";

const sourceSchema = z
  .object({
    name: z.string(),
    kind: z.string(),
    metadata: z.string(),
  })
  .strict();
export type sourceType = z.infer<typeof sourceSchema>;

export class Source extends BaseData<sourceType> {
  constructor(obj: BaseDataFields<sourceType>) {
    sourceSchema.parse(obj.data);
    super(obj);
  }
}
