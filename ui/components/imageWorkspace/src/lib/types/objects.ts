import type { BBox, Mask } from "@pixano/core";

type BaseObjectContent = {
  name: string;
  id: string;
  properties: {
    label: string[];
  };
  editing?: boolean;
};

export type BoxObjectContent = BaseObjectContent & {
  type: "box";
  boundingBox: BBox;
};

export type MaskObjectContent = BaseObjectContent & {
  type: "mask";
  mask: Mask;
};

export type ObjectContent = BoxObjectContent | MaskObjectContent;
