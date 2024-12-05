import type { BBox } from "../datasetTypes";
import { AnnotationConnection } from "./AnnotationConnection";
import type { TaggedText } from "./TaggedText";

export class TextBBoxConnection extends AnnotationConnection {
  constructor(
    private taggedText: TaggedText,
    private bbox: BBox,
  ) {
    super(taggedText, bbox);
  }
}
