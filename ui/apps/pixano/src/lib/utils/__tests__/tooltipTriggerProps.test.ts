/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it } from "vitest";

import { passiveTriggerProps } from "$lib/utils/tooltipTriggerProps";

describe("passiveTriggerProps", () => {
  it("drops the button type and the tab stop, keeps the rest", () => {
    const onpointerenter = () => {};
    const props = {
      id: "trigger-1",
      type: "button",
      tabindex: 0,
      "data-state": "closed",
      "aria-describedby": "content-1",
      onpointerenter,
    };

    const passive = passiveTriggerProps(props);

    expect(passive).toEqual({
      id: "trigger-1",
      "data-state": "closed",
      "aria-describedby": "content-1",
      onpointerenter,
    });
    expect("type" in passive).toBe(false);
    expect("tabindex" in passive).toBe(false);
  });
});
