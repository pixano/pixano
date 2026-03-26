import type { Component } from 'svelte';

/** Grid position and size for a widget instance */
export interface WidgetLayout {
	x: number;
	y: number;
	w: number;
	h: number;
	minW?: number;
	minH?: number;
}

/** Runtime context passed to extension lifecycle hooks */
export interface WidgetContext {
	widgetId: string;
	container: HTMLElement;
	options: Record<string, unknown>;
	storage: Record<string, unknown>;
}

/** A command that operates on a widget context */
export type WidgetCommand = (ctx: WidgetContext) => boolean;

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
	TStorage extends Record<string, unknown> = Record<string, unknown>
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

	/** Called when extension is registered with the registry */
	onCreate?: (ctx: WidgetContext) => void;

	/** Called when the widget's component is mounted in the DOM */
	onMount?: (ctx: WidgetContext) => void;

	/** Called when GridStack reports a resize */
	onResize?: (ctx: WidgetContext, width: number, height: number) => void;

	/** Called when the widget is removed from workspace */
	onDestroy?: (ctx: WidgetContext) => void;

	/** Commands this extension provides */
	addCommands?: () => Record<string, (...args: unknown[]) => WidgetCommand>;

	/** Child extensions this extension bundles (composition pattern) */
	addExtensions?: () => WidgetExtensionConfig[];
}

/** A widget instance in the workspace */
export interface WidgetInstance {
	id: string;
	extensionName: string;
	title: string;
	layout: WidgetLayout;
	options: Record<string, unknown>;
	data?: Record<string, unknown>;
}

/** A workspace preset (named layout configuration) */
export interface WorkspacePreset {
	name: string;
	widgets: Omit<WidgetInstance, 'id'>[];
}
