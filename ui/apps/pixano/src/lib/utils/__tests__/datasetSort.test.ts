/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it } from "vitest";

import { sortDatasets } from "$lib/utils/datasetSort";

const ds = (name: string, creation_date: string) => ({ name, creation_date });

describe("sortDatasets", () => {
  it("date mode puts the NEWEST dataset first", () => {
    const sorted = sortDatasets(
      [
        ds("old", "2026-01-01T00:00:00+00:00"),
        ds("newest", "2026-07-20T00:00:00+00:00"),
        ds("mid", "2026-03-15T00:00:00+00:00"),
      ],
      "creation_date",
    );
    expect(sorted.map((d) => d.name)).toEqual(["newest", "mid", "old"]);
  });

  it("date mode sorts datasets without a creation date LAST, alphabetically", () => {
    const sorted = sortDatasets(
      [ds("legacy_b", ""), ds("dated", "2026-05-01T00:00:00+00:00"), ds("legacy_a", "")],
      "creation_date",
    );
    expect(sorted.map((d) => d.name)).toEqual(["dated", "legacy_a", "legacy_b"]);
  });

  it("name mode sorts alphabetically regardless of dates", () => {
    const sorted = sortDatasets(
      [ds("bravo", "2026-07-01T00:00:00+00:00"), ds("alpha", ""), ds("charlie", "2026-01-01T00:00:00+00:00")],
      "name",
    );
    expect(sorted.map((d) => d.name)).toEqual(["alpha", "bravo", "charlie"]);
  });

  it("does not mutate the input list", () => {
    const input = [ds("b", ""), ds("a", "")];
    sortDatasets(input, "name");
    expect(input.map((d) => d.name)).toEqual(["b", "a"]);
  });
});
