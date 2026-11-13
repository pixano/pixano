/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it } from "vitest";

import { formatStatisticValue, NO_VALUE } from "../format";

describe("a statistic's value as a column shows it", () => {
  it("keeps a count whole, and a decimal readable", () => {
    expect(formatStatisticValue(3)).toBe("3");
    expect(formatStatisticValue(1234.5678)).toBe((1234.57).toLocaleString());
    expect(formatStatisticValue(0.0012345)).toBe(
      (0.00123).toLocaleString(undefined, { maximumSignificantDigits: 3 }),
    );
  });

  it("shows a dash where a record has no value", () => {
    expect(formatStatisticValue("")).toBe(NO_VALUE);
    expect(formatStatisticValue(null)).toBe(NO_VALUE);
  });
});
