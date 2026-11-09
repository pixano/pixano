/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it } from "vitest";

import { toRawAnnotation } from "$lib/api/adapters";
import type { RecordComponentResponse } from "$lib/api/restTypes";
import { Annotation } from "$lib/types/dataset";
import { sortChilds } from "$lib/utils/entityLookupUtils";

// The order an entity's card lists its annotations in, which the review's keys follow.

/** The fields of a row of each table, past its id and provenance. */
const FIELDS: Record<"bboxes" | "masks", Record<string, unknown>> = {
  bboxes: { coords: [0.1, 0.1, 0.2, 0.2], format: "xywh", is_normalized: true, confidence: 0.8 },
  masks: { size: [2, 2], counts: "04" },
};

function read(table: "bboxes" | "masks", id: string, row: Record<string, unknown> = {}) {
  const component = {
    id,
    record_id: "record-1",
    view_id: "view-1",
    entity_id: "entity-1",
    source_type: "model",
    source_name: "detection",
    source_metadata: "{}",
    created_at: "",
    updated_at: "",
    ...FIELDS[table],
    ...row,
  } as RecordComponentResponse;
  const raw = toRawAnnotation(component, new Map([["view-1", "image"]]), table);
  return Annotation.deepCreateInstanceArray({ [table]: [raw] })[table][0];
}

const order = (annotations: Annotation[]): string[] =>
  [...annotations].sort((a, b) => sortChilds(a, b, ["image"])).map((annotation) => annotation.id);

describe("the order of an entity's card", () => {
  it("puts a box before its mask", () => {
    expect(order([read("masks", "1"), read("bboxes", "2")])).toEqual(["2", "1"]);
  });

  it("orders annotations of a kind by id", () => {
    expect(order([read("bboxes", "2"), read("bboxes", "1")])).toEqual(["1", "2"]);
  });

  it("orders them by id when only one has a name", () => {
    expect(order([read("bboxes", "2", { name: "a" }), read("bboxes", "1")])).toEqual(["1", "2"]);
  });

  it("orders them by name when both have one", () => {
    expect(order([read("bboxes", "1", { name: "b" }), read("bboxes", "2", { name: "a" })])).toEqual(
      ["2", "1"],
    );
  });
});
