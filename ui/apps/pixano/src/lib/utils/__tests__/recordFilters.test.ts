/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it } from "vitest";

import {
  looksLikeRawSql,
  parseFilter,
  parseFilters,
  serializeFilter,
  serializeFilters,
  type RecordFilter,
} from "$lib/utils/recordFilters";

describe("serializeFilter / parseFilter round-trip", () => {
  it("serializes a scalar filter", () => {
    expect(serializeFilter({ col: "split", op: "eq", values: ["train"] })).toBe("split:eq:train");
  });

  it("serializes a list filter with comma-joined values", () => {
    expect(serializeFilter({ col: "split", op: "in", values: ["train", "val"] })).toBe(
      "split:in:train,val",
    );
  });

  it("escapes literal commas in list values", () => {
    expect(serializeFilter({ col: "caption", op: "in", values: ["a,b", "c"] })).toBe(
      "caption:in:a\\,b,c",
    );
  });

  it("parses a scalar token", () => {
    expect(parseFilter("split:eq:train")).toEqual({ col: "split", op: "eq", values: ["train"] });
  });

  it("keeps a colon inside a scalar value", () => {
    expect(parseFilter("comment:eq:10:30:00")).toEqual({
      col: "comment",
      op: "eq",
      values: ["10:30:00"],
    });
  });

  it("splits list values and unescapes commas", () => {
    expect(parseFilter("caption:in:a\\,b,c")).toEqual({
      col: "caption",
      op: "in",
      values: ["a,b", "c"],
    });
  });

  it("returns null for a malformed token", () => {
    expect(parseFilter("nocolons")).toBeNull();
    expect(parseFilter("only:one")).toBeNull();
  });

  it("round-trips a set of filters", () => {
    const filters: RecordFilter[] = [
      { col: "split", op: "eq", values: ["train"] },
      { col: "score", op: "gte", values: ["0.5"] },
      { col: "tags", op: "in", values: ["a,b", "c"] },
    ];
    expect(parseFilters(serializeFilters(filters))).toEqual(filters);
  });

  it("drops unparseable tokens when parsing a list", () => {
    expect(parseFilters(["split:eq:train", "garbage"])).toEqual([
      { col: "split", op: "eq", values: ["train"] },
    ]);
  });
});

describe("looksLikeRawSql", () => {
  it("recognizes structured tokens as NOT raw SQL", () => {
    expect(looksLikeRawSql("split:eq:train")).toBe(false);
    expect(looksLikeRawSql("caption:contains:a dog")).toBe(false);
  });

  it("recognizes raw SQL clauses", () => {
    expect(looksLikeRawSql("split = 'train'")).toBe(true);
    expect(looksLikeRawSql("score > 0.5 AND split = 'val'")).toBe(true);
    expect(looksLikeRawSql("caption LIKE '%dog%'")).toBe(true);
  });

  it("treats empty input as not raw SQL", () => {
    expect(looksLikeRawSql("")).toBe(false);
    expect(looksLikeRawSql("   ")).toBe(false);
  });
});
