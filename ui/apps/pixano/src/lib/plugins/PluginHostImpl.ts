/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { Command } from "$lib/commands";
import type { Document, DocumentQuery, NodeId } from "$lib/document";
import type { ComputeJob } from "$lib/services";
import type { ToolFSM } from "$lib/tools";

import type {
  Capability,
  ModelInvocationParams,
  PanelDefinition,
  Plugin,
  PluginContext,
  PluginHost,
  PluginStatus,
  Unsubscribe,
} from "$lib/types/plugins";

interface PluginEntry {
  plugin: Plugin;
  status: PluginStatus;
}

/** Options for creating a PluginHost. */
export interface PluginHostOptions {
  /** Called when a plugin proposes a command. */
  onCommand: (command: Command) => void;
  /** Called when a plugin registers a tool. */
  onToolRegistered: (tool: ToolFSM) => void;
  /** Called when a plugin registers a panel. */
  onPanelRegistered: (panel: PanelDefinition) => void;
  /** Provides the current document snapshot. */
  getDocument: () => Document;
  /** Provides current selected IDs. */
  getSelectedIds: () => ReadonlySet<NodeId>;
  /** Sets the selection. */
  setSelection: (ids: ReadonlySet<NodeId>) => void;
}

/**
 * Manages plugin lifecycle with crash isolation.
 *
 * Each plugin receives a sandboxed PluginContext that validates
 * all operations against the plugin's declared capabilities.
 */
export class PluginHostImpl implements PluginHost {
  private readonly plugins = new Map<string, PluginEntry>();
  private readonly options: PluginHostOptions;

  constructor(options: PluginHostOptions) {
    this.options = options;
  }

  register(plugin: Plugin): void {
    if (this.plugins.has(plugin.manifest.id)) {
      throw new Error(`Plugin already registered: ${plugin.manifest.id}`);
    }
    this.plugins.set(plugin.manifest.id, { plugin, status: "registered" });
  }

  unregister(pluginId: string): void {
    const entry = this.plugins.get(pluginId);
    if (!entry) return;
    if (entry.status === "active") {
      throw new Error(`Cannot unregister active plugin: ${pluginId}. Deactivate it first.`);
    }
    this.plugins.delete(pluginId);
  }

  async activate(pluginId: string): Promise<void> {
    const entry = this.plugins.get(pluginId);
    if (!entry) throw new Error(`Plugin not found: ${pluginId}`);
    if (entry.status === "active") return;

    const context = this.createContext(entry.plugin);

    try {
      await entry.plugin.activate(context);
      entry.status = "active";
    } catch (error) {
      console.error(`Plugin activation failed: ${pluginId}`, error);
      entry.status = "failed";
    }
  }

  async deactivate(pluginId: string): Promise<void> {
    const entry = this.plugins.get(pluginId);
    if (!entry) throw new Error(`Plugin not found: ${pluginId}`);
    if (entry.status !== "active") return;

    try {
      await entry.plugin.deactivate();
    } catch (error) {
      console.error(`Plugin deactivation error: ${pluginId}`, error);
    }
    entry.status = "deactivated";
  }

  getStatus(pluginId: string): PluginStatus | undefined {
    return this.plugins.get(pluginId)?.status;
  }

  getAll(): ReadonlyArray<{ plugin: Plugin; status: PluginStatus }> {
    return [...this.plugins.values()];
  }

  private createContext(plugin: Plugin): PluginContext {
    const caps = new Set(plugin.manifest.capabilities);
    const options = this.options;

    const requireCapability = (cap: Capability, operation: string) => {
      if (!caps.has(cap)) {
        throw new Error(
          `Plugin "${plugin.manifest.id}" lacks capability "${cap}" for operation: ${operation}`,
        );
      }
    };

    return {
      get document(): Document {
        requireCapability("document:read", "document access");
        return options.getDocument();
      },

      // eslint-disable-next-line @typescript-eslint/no-unused-vars
      subscribe(query: DocumentQuery): Unsubscribe {
        requireCapability("document:read", "subscribe");
        // Subscription implementation will be connected to the store
        return () => {};
      },

      proposeCommand(command: Command): void {
        requireCapability("document:write", "proposeCommand");
        try {
          options.onCommand(command);
        } catch (error) {
          console.error(`Plugin "${plugin.manifest.id}" command failed:`, error);
        }
      },

      registerTool(tool: ToolFSM): void {
        requireCapability("ui:tool", "registerTool");
        options.onToolRegistered(tool);
      },

      registerPanel(panel: PanelDefinition): void {
        requireCapability("ui:panel", "registerPanel");
        options.onPanelRegistered(panel);
      },

      // eslint-disable-next-line @typescript-eslint/no-unused-vars
      runModel(_params: ModelInvocationParams): ComputeJob {
        requireCapability("ai:invoke", "runModel");
        // Will be connected to ComputeService in Phase 5
        throw new Error("ComputeService not yet connected");
      },

      // eslint-disable-next-line @typescript-eslint/no-unused-vars
      getAsset(_uri: string): Promise<Blob> {
        requireCapability("storage:read", "getAsset");
        // Will be connected to AssetManager in Phase 5
        return Promise.reject(new Error("AssetManager not yet connected"));
      },

      get selectedIds(): ReadonlySet<NodeId> {
        return options.getSelectedIds();
      },

      setSelection(ids: ReadonlySet<NodeId>): void {
        options.setSelection(ids);
      },
    };
  }
}
