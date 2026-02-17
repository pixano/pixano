/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { ToolFSM, ToolRegistry } from "../types";

/**
 * Simple in-memory tool registry.
 */
export class ToolRegistryImpl implements ToolRegistry {
  private readonly tools = new Map<string, ToolFSM>();

  register(tool: ToolFSM): void {
    if (this.tools.has(tool.id)) {
      throw new Error(`Tool already registered: ${tool.id}`);
    }
    this.tools.set(tool.id, tool);
  }

  unregister(toolId: string): void {
    this.tools.delete(toolId);
  }

  get(toolId: string): ToolFSM | undefined {
    return this.tools.get(toolId);
  }

  getAll(): ReadonlyArray<ToolFSM> {
    return [...this.tools.values()];
  }
}
