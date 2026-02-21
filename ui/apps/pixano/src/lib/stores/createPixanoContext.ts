/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { CommandProcessor } from "$lib/commands";
import { CommandProcessorImpl } from "$lib/commands";
import type { Document } from "$lib/document";
import type { ToolFSM } from "$lib/tools";

import { CommandBridgeImpl } from "./CommandBridgeImpl.svelte";
import { DocumentStoreImpl } from "./DocumentStoreImpl.svelte";
import { ToolBridgeImpl } from "./ToolBridgeImpl.svelte";

export interface PixanoContext {
  readonly documentStore: DocumentStoreImpl;
  readonly commandBridge: CommandBridgeImpl;
  readonly toolBridge: ToolBridgeImpl;
}

export interface CreatePixanoContextOptions {
  document: Document;
  initialTool: ToolFSM;
  commandProcessor?: CommandProcessor;
}

/**
 * Creates the full Pixano reactive context.
 *
 * This is the main entry point for wiring up the new architecture.
 * Call this once when loading a dataset item.
 */
export function createPixanoContext(options: CreatePixanoContextOptions): PixanoContext {
  const processor = options.commandProcessor ?? new CommandProcessorImpl();
  const documentStore = new DocumentStoreImpl(options.document);
  const commandBridge = new CommandBridgeImpl(processor, documentStore);
  const toolBridge = new ToolBridgeImpl(options.initialTool, commandBridge, documentStore);

  return { documentStore, commandBridge, toolBridge };
}
