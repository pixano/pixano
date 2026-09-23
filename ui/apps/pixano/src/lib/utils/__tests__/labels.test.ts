/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it } from "vitest";

import { humanizeFieldName, humanizeShapeType, humanizeTableName } from "../labels";

describe("humanizeShapeType", () => {
  it("maps known shape tokens to human names", () => {
    expect(humanizeShapeType("bbox")).toBe("bounding box");
    expect(humanizeShapeType("textSpan")).toBe("text span");
    expect(humanizeShapeType("mask")).toBe("mask");
    expect(humanizeShapeType("keypoints")).toBe("keypoints");
    expect(humanizeShapeType("polygon")).toBe("polygon");
    expect(humanizeShapeType("polyline")).toBe("polyline");
    expect(humanizeShapeType("track")).toBe("track");
  });

  it("falls back to spaced lowercase for unknown tokens", () => {
    expect(humanizeShapeType("customShape")).toBe("custom shape");
  });
});

describe("humanizeFieldName", () => {
  it("title-cases snake_case", () => {
    expect(humanizeFieldName("category_name")).toBe("Category name");
  });

  it("splits camelCase", () => {
    expect(humanizeFieldName("numInstances")).toBe("Num instances");
  });

  it("handles single words and empty strings", () => {
    expect(humanizeFieldName("name")).toBe("Name");
    expect(humanizeFieldName("")).toBe("");
  });
});

describe("humanizeTableName", () => {
  it("humanizes table names for group headers", () => {
    expect(humanizeTableName("entities")).toBe("Entities");
    expect(humanizeTableName("text_spans")).toBe("Text spans");
  });
});
