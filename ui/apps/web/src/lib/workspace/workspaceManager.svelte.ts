/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { WidgetInstance, WidgetLayout } from '$lib/extensions/types.js';
import type { WidgetRegistry } from '$lib/extensions/WidgetRegistry.js';
import type { WorkspacePreset } from '$lib/extensions/types.js';
import * as api from '$lib/api';
import { WorkspaceType } from '$lib/types/dataset';
import type { ImageResponse } from '$lib/api/restTypes';

/**
 * Reactive workspace manager using Svelte 5 $state runes.
 * Manages the collection of widget instances and bridges
 * between the WidgetRegistry (blueprints) and GridStack (DOM).
 */
export class WorkspaceManager {
	widgets = $state<WidgetInstance[]>([]);
	editMode = $state(true);
	presetName = $state('Default');
	datasetId = $state<string | null>("NSn7gHtkh6366dWXz6kdwF");
	recordId = $state<string | null>("85dMNwowyc7ZXQrWNSyBmc");

	widgetCount = $derived(this.widgets.length);

	private registry: WidgetRegistry;
	private storageMap: Map<string, Record<string, unknown>> = new Map();

	constructor(registry: WidgetRegistry) {
		this.registry = registry;
	}

	/** Add a new widget instance for the given extension name */
	addWidget(extensionName: string, overrides?: Partial<WidgetInstance>): WidgetInstance | null {
		const config = this.registry.get(extensionName);
		if (!config) {
			console.warn(`Extension "${extensionName}" not found in registry`);
			return null;
		}

		const options = config.addOptions?.() ?? {};
		const storage = config.addStorage?.() ?? {};

		const widget: WidgetInstance = {
			id: crypto.randomUUID(),
			extensionName,
			title: overrides?.title ?? config.label,
			layout: overrides?.layout ?? { ...config.defaultLayout },
			options: { ...options, ...overrides?.options },
			data: overrides?.data
		};

		this.storageMap.set(widget.id, storage);
		this.widgets.push(widget);
		return widget;
	}

	/** Remove a widget by ID */
	removeWidget(id: string): void {
		this.storageMap.delete(id);
		this.widgets = this.widgets.filter((w) => w.id !== id);
	}

	/** Update a widget's grid layout */
	updateLayout(id: string, layout: Partial<WidgetLayout>): void {
		const widget = this.widgets.find((w) => w.id === id);
		if (widget) {
			widget.layout = { ...widget.layout, ...layout };
		}
	}

	/** Get the mutable storage for a widget instance */
	getStorage(id: string): Record<string, unknown> | undefined {
		return this.storageMap.get(id);
	}

	/** Apply a workspace preset, replacing all current widgets */
	applyPreset(preset: WorkspacePreset): void {
		// Clear existing
		this.storageMap.clear();
		this.widgets = [];
		this.presetName = preset.name;

		// Add widgets from preset
		for (const template of preset.widgets) {
			this.addWidget(template.extensionName, template);
		}
	}

	async selectRecordInDataset(datasetId: string, recordId: string): Promise<void> {
		const dataset = await api.getDataset(datasetId);
		if(dataset.info.workspace !== WorkspaceType.IMAGE) {
			throw new Error("Dataset is not an image dataset");
		}
		const TOREMOVE = {
			extensionName: 'image',
			title: '2D Canvas',
			layout: { x: 0, y: 0, w: 5, h: 5 },
			options: {},
			data: { imageUrl: '/datasets/NSn7gHtkh6366dWXz6kdwF/images/NSgX5APmfXnQwYdsdHPPbA/blob' }
		}
		const images = await api.loadImages(datasetId, recordId);
		images.forEach(image => {
			this.addWidget('image', {
				...TOREMOVE,
				data: { imageUrl: image.src }
			});
		});
	}
}
