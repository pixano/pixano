/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

// ============================================================
// @pixano/plugins — Plugin host and capability API
// ============================================================

import type { Command } from "$lib/commands";
import type { Document, DocumentQuery, NodeId } from "$lib/document";
import type { ComputeJob, Unsubscribe } from "$lib/services";
import type { ToolFSM } from "$lib/tools";

export type { Unsubscribe };

// --------------- Capabilities ---------------

/** Fine-grained capabilities that plugins can request. */
export type Capability =
  | "document:read"
  | "document:write"
  | "ai:invoke"
  | "storage:read"
  | "ui:panel"
  | "ui:tool";

// --------------- Plugin Manifest ---------------

export type PluginType = "tool" | "panel" | "ai-provider" | "codec";

/** Static metadata describing a plugin. */
export interface PluginManifest {
  readonly id: string;
  readonly name: string;
  readonly version: string;
  readonly apiVersion: string;
  readonly type: PluginType;
  readonly capabilities: readonly Capability[];
  readonly description?: string;
}

// --------------- Panel Definition ---------------

/** A panel contributed by a plugin. */
export interface PanelDefinition {
  readonly id: string;
  readonly name: string;
  readonly icon: string;
  readonly position: "left" | "right" | "bottom";
  readonly component: unknown; // Svelte component reference — opaque to the plugin system
}

// --------------- Model Invocation ---------------

export interface ModelInvocationParams {
  readonly modelId: string;
  readonly input: unknown;
  readonly options?: Readonly<Record<string, unknown>>;
}

// --------------- Plugin Context ---------------

/**
 * The sandboxed API surface exposed to plugins.
 *
 * All interactions with the core system go through this context.
 * Operations are validated against the plugin's declared capabilities.
 */
export interface PluginContext {
  // --- Document access ---
  readonly document: Document;
  subscribe(query: DocumentQuery): Unsubscribe;

  // --- Mutations (requires "document:write") ---
  proposeCommand(command: Command): void;

  // --- Tool registration (requires "ui:tool") ---
  registerTool(tool: ToolFSM): void;

  // --- Panel registration (requires "ui:panel") ---
  registerPanel(panel: PanelDefinition): void;

  // --- AI invocation (requires "ai:invoke") ---
  runModel(params: ModelInvocationParams): ComputeJob;

  // --- Asset access (requires "storage:read") ---
  getAsset(uri: string): Promise<Blob>;

  // --- Selection ---
  readonly selectedIds: ReadonlySet<NodeId>;
  setSelection(ids: ReadonlySet<NodeId>): void;
}

// --------------- Plugin ---------------

export type PluginStatus = "registered" | "active" | "failed" | "deactivated";

/**
 * A plugin lifecycle interface.
 * Plugins are activated with a PluginContext and can register tools, panels, etc.
 */
export interface Plugin {
  readonly manifest: PluginManifest;
  activate(context: PluginContext): void | Promise<void>;
  deactivate(): void | Promise<void>;
}

// --------------- Plugin Host ---------------

/**
 * Manages the plugin lifecycle: registration, activation, deactivation.
 * Provides crash isolation — a failing plugin does not affect others.
 */
export interface PluginHost {
  register(plugin: Plugin): void;
  unregister(pluginId: string): void;
  activate(pluginId: string): Promise<void>;
  deactivate(pluginId: string): Promise<void>;
  getStatus(pluginId: string): PluginStatus | undefined;
  getAll(): ReadonlyArray<{ plugin: Plugin; status: PluginStatus }>;
}
