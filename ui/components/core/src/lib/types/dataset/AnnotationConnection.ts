import type { Annotation } from "../datasetTypes";

export class AnnotationConnection {
  constructor(
    private annotation1: Annotation,
    private annotation2: Annotation,
  ) {}
}
