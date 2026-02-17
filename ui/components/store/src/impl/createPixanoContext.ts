/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { CommandProcessor } from "@pixano/commands";
import { CommandProcessorImpl } from "@pixano/commands";
import type { Document } from "@pixano/document";
import type { ToolFSM } from "@pixano/tools";

import { CommandBridgeImpl } from "./CommandBridgeImpl";
import { DocumentStoreImpl } from "./DocumentStoreImpl";
import { ToolBridgeImpl } from "./ToolBridgeImpl";

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
