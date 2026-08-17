/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { Component } from "svelte";

import type { RecordWidgetSeed, SeedContext } from "$lib/workspace/recordSeed.js";

/** Grid position and size for a widget instance */
export interface WidgetLayout {
  x: number;
  y: number;
  w: number;
  h: number;
  minW?: number;
  minH?: number;
}

/** Props interface that all widget components must accept */
export interface WidgetComponentProps<TOptions = Record<string, unknown>> {
  widgetId: string;
  options: TOptions;
  data?: Record<string, unknown>;
}

/**
 * Extension config - the blueprint for a widget type.
 * Modeled after TipTap's Extension.create() pattern.
 */
export interface WidgetExtensionConfig<
  TOptions extends Record<string, unknown> = Record<string, unknown>,
  TStorage extends Record<string, unknown> = Record<string, unknown>,
> {
  /** Unique identifier, e.g. 'image', 'text', 'point-cloud' */
  name: string;

  /** Display name shown in the widget palette */
  label: string;

  /** Lucide icon name for the palette */
  icon: string;

  /** Higher priority = appears first in palette */
  priority?: number;

  /** Default grid layout when adding this widget */
  defaultLayout: WidgetLayout;

  /** The Svelte 5 component to render inside the widget frame */
  component: Component<WidgetComponentProps<TOptions>>;

  /** Factory for default options (like TipTap's addOptions) */
  addOptions?: () => TOptions;

  /** Factory for default per-instance mutable storage (like TipTap's addStorage) */
  addStorage?: () => TStorage;

  /*
   * There is deliberately no lifecycle hook here (no onCreate/onMount/onResize/
   * onDestroy) and no addCommands. An earlier version declared them and nothing
   * ever invoked them, which made the contract lie about what a widget could
   * rely on. A widget component owns its own lifecycle with Svelte's `onMount` /
   * `onDestroy` and a `ResizeObserver` — see `ImageWidget.svelte` — which is one
   * mechanism instead of two. Reintroduce a hook only with the call site that
   * fires it.
   */

  /** Child extensions this extension bundles (composition pattern) */
  addExtensions?: () => WidgetExtensionConfig[];

  /**
   * Optional: claim a (record, view) pair and produce a seed describing how
   * to instantiate this widget for it. See `lib/workspace/recordSeed.ts`
   * for the rationale. Return `null` if this view isn't ours so the
   * `WorkspaceManager` can ask the next extension.
   */
  addRecordSeed?: (ctx: SeedContext) => Promise<RecordWidgetSeed<TStorage> | null>;
}

/** A widget instance in the workspace */
export interface WidgetInstance {
  id: string;
  extensionName: string;
  title: string;
  layout: WidgetLayout;
  options: Record<string, unknown>;
  data?: Record<string, unknown>;
  hidden?: boolean;
  /**
   * Dataset view this widget renders, set by `RecordLoader` for record-seeded
   * widgets and absent for ones added from the palette. It is the widget's only
   * identifier that survives a record switch, so it keys the per-dataset layout
   * preference (see `workspace/datasetLayout.ts`).
   */
  viewName?: string;
}

/** A workspace preset (named layout configuration) */
export interface WorkspacePreset {
  name: string;
  widgets: Omit<WidgetInstance, "id">[];
}
