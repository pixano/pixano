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
		const workspace = dataset.info.workspace;

		if (workspace === WorkspaceType.IMAGE) {
			const TOREMOVE_IMAGE = {
				extensionName: 'image',
				title: '2D Canvas',
				layout: { x: 0, y: 0, w: 5, h: 5 },
				options: {},
			};
			const images = await api.loadImages(datasetId, recordId);
			images.forEach(image => {
				this.addWidget('image', {
					...TOREMOVE_IMAGE,
					data: { imageUrl: image.src }
				});
			});
		} else if (workspace === WorkspaceType.PCL_3D) {
			const TOREMOVE_PCL_IMAGE3 = {
				extensionName: 'image',
				title: 'cam_front',
				layout: { x: 0, y: 0, w: 5, h: 4 },
				options: {},
			};
			const TOREMOVE_PCL_CLOUD = {
				extensionName: 'point-cloud',
				title: '3D Viewer',
				layout: { x: 5, y: 0, w: 5, h: 4 },
				options: {},
			};
			const TOREMOVE_PCL_IMAGE2 = {
				extensionName: 'image',
				title: 'cam_back_right',
				layout: { x: 10, y: 0, w: 5, h: 4 },
				options: {},
			};
			const TOREMOVE_PCL_IMAGE1 = {
				extensionName: 'image',
				title: 'cam_back',
				layout: { x: 0, y: 4, w: 5, h: 4 },
				options: {},
			};
			const [camImage1, camImage2, camImage3, pointCloud] = await Promise.all([
				api.loadImageByLogicalName(datasetId, recordId, 'cam_back'),
				api.loadImageByLogicalName(datasetId, recordId, 'cam_back_left'),
				api.loadImageByLogicalName(datasetId, recordId, 'cam_front'),
				api.loadPointCloudByLogicalName(datasetId, recordId, 'point_cloud'),
			]);
			if (camImage1) {
				this.addWidget('image', {
					...TOREMOVE_PCL_IMAGE1,
					data: { imageUrl: camImage1.src }
				});
			}
			if (camImage2) {
				this.addWidget('image', {
					...TOREMOVE_PCL_IMAGE2,
					data: { imageUrl: camImage2.src }
				});
			}
			if (camImage3) {
				this.addWidget('image', {
					...TOREMOVE_PCL_IMAGE3,
					data: { imageUrl: camImage3.src }
				});
			}
			if (pointCloud) {
				this.addWidget('point-cloud', {
					...TOREMOVE_PCL_CLOUD,
					data: { pointCloudUrl: pointCloud.src }
				});
			}
		} else {
			throw new Error(`Workspace type '${workspace}' is not supported`);
		}
	}
}
