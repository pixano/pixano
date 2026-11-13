/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it } from "vitest";

import { explorerSearch, isExplorerView } from "../explorerSearch";

describe("explorerSearch", () => {
  it("finds a plain text in the records' fields", () => {
    expect(explorerSearch("dog", false, "", false)).toEqual({
      ranking: false,
      runsRanking: false,
      fieldText: "dog",
    });
  });

  it("runs a semantic search, whose text is no field's", () => {
    expect(explorerSearch("a dog", true, "", false)).toEqual({
      ranking: true,
      runsRanking: true,
      fieldText: undefined,
    });
  });

  it("runs a search of look-alikes whatever the text", () => {
    expect(explorerSearch("", false, "r1", false).runsRanking).toBe(true);
  });

  it("runs no ranking search for the overview, and still finds no field text in it", () => {
    expect(explorerSearch("a dog", true, "", true)).toEqual({
      ranking: true,
      runsRanking: false,
      fieldText: undefined,
    });
    expect(explorerSearch("dog", false, "", true).fieldText).toBe("dog");
  });

  it("asks nothing of an empty text", () => {
    expect(explorerSearch("", true, "", false)).toEqual({
      ranking: false,
      runsRanking: false,
      fieldText: undefined,
    });
  });
});

describe("isExplorerView", () => {
  it("tells the explorer's views from other names", () => {
    expect(["grid", "table", "overview", "gallery", null].map(isExplorerView)).toEqual([
      true,
      true,
      true,
      false,
      false,
    ]);
  });
});
