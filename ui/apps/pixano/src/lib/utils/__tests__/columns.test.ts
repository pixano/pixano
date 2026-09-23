/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it } from "vitest";

import { formatColumnLabel } from "../columns";

describe("formatColumnLabel", () => {
  it("title-cases every underscore-separated word", () => {
    expect(formatColumnLabel("created_at")).toBe("Created At");
    expect(formatColumnLabel("created_at_utc")).toBe("Created At Utc");
  });

  it("strips the leading underscore of system columns", () => {
    expect(formatColumnLabel("_distance")).toBe("Distance");
  });

  it("handles single words and empty strings", () => {
    expect(formatColumnLabel("id")).toBe("Id");
    expect(formatColumnLabel("split")).toBe("Split");
    expect(formatColumnLabel("")).toBe("");
  });
});
