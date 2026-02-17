/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { NodeId } from "@pixano/document";
import { createEmptyDocument } from "@pixano/document/test/helpers";

import type { ToolContext } from "../src/types";

/** Create a minimal ToolContext for testing. */
export function createTestContext(overrides?: Partial<ToolContext>): ToolContext {
  return {
    document: createEmptyDocument(),
    selectedIds: new Set<NodeId>(),
    viewName: "image",
    canvasWidth: 800,
    canvasHeight: 600,
    ...overrides,
  };
}
