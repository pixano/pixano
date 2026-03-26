<script lang="ts">
	import 'gridstack/dist/gridstack.min.css';
	import { onMount, onDestroy, mount, unmount } from 'svelte';
	import { GridStack, type GridStackNode } from 'gridstack';
	import type { WorkspaceManager } from '$lib/workspace/workspaceManager.svelte.js';
	import type { WidgetRegistry } from '$lib/extensions/WidgetRegistry.js';
	import type { WidgetInstance } from '$lib/extensions/types.js';
	import WidgetFrame from './WidgetFrame.svelte';

	interface Props {
		manager: WorkspaceManager;
		registry: WidgetRegistry;
	}

	let { manager, registry }: Props = $props();

	let grid: GridStack;
	let mountedWidgets: Map<string, Record<string, unknown>> = new Map();
	let lastManipulationEvent = 0;

	function mountWidget(widget: WidgetInstance) {
		const config = registry.get(widget.extensionName);
		if (!config) return;

		const element = document.createElement('div');
		element.dataset.widgetId = widget.id;
		grid.el.appendChild(element);

		const component = mount(WidgetFrame, {
			target: element,
			props: {
				widget,
				config,
				onRemove: () => manager.removeWidget(widget.id)
			}
		});

		mountedWidgets.set(widget.id, component);

		grid.makeWidget(element, {
			x: widget.layout.x,
			y: widget.layout.y,
			w: widget.layout.w,
			h: widget.layout.h,
			minH: config.defaultLayout.minH ?? 2,
			minW: config.defaultLayout.minW ?? 2
		});
	}

	function unmountWidget(widgetId: string) {
		const component = mountedWidgets.get(widgetId);
		if (!component) return;

		unmount(component);
		mountedWidgets.delete(widgetId);

		const element = grid.getGridItems().find((i) => i.dataset.widgetId === widgetId);
		if (element) {
			grid.removeWidget(element, false);
		}
	}

	function parseLayoutFromElement(element: HTMLElement) {
		return {
			x: parseInt(element.getAttribute('gs-x') ?? '0'),
			y: parseInt(element.getAttribute('gs-y') ?? '0'),
			w: parseInt(element.getAttribute('gs-w') ?? '0'),
			h: parseInt(element.getAttribute('gs-h') ?? '0')
		};
	}

	function onGridMoveOrResize() {
		lastManipulationEvent = Date.now();
	}

	function onGridItemsChange(_: Event, items: GridStackNode[]) {
		if (Date.now() - lastManipulationEvent > 10) return;

		for (const item of items) {
			const element = item.el;
			if (!element) continue;

			const widgetId = element.dataset.widgetId;
			if (!widgetId) continue;

			const layout = parseLayoutFromElement(element);
			manager.updateLayout(widgetId, layout);
		}
	}

	function onGridItemAdded(_: Event, items: GridStackNode[]) {
		for (const item of items) {
			const element = item.el;
			if (!element) continue;

			const child = element.firstElementChild;
			if (!child || !child.classList.contains('sidebar-draggable')) continue;

			const extensionName = child.getAttribute('data-extension-name');
			if (!extensionName) continue;

			const layout = parseLayoutFromElement(element);
			grid.removeWidget(element, false);

			const widget = manager.addWidget(extensionName, { layout });
			if (widget) {
				mountWidget(widget);
			}
		}
	}

	onMount(() => {
		grid = GridStack.init({
			cellHeight: 'auto',
			acceptWidgets: true,
			handleClass: 'grid-stack-handle',
			margin: 5,
			animate: false,
			float: true
		});

		grid.on('added', onGridItemAdded);
		grid.on('dragstop resizestop', onGridMoveOrResize);
		grid.on('change', onGridItemsChange);

		// Mount initial widgets
		for (const widget of manager.widgets) {
			mountWidget(widget);
		}
	});

	// Sync editMode with GridStack static mode
	$effect(() => {
		if (grid) {
			grid.setStatic(!manager.editMode);
		}
	});

	// React to widget additions/removals from manager
	$effect(() => {
		if (!grid) return;

		const currentIds = new Set(mountedWidgets.keys());
		const managerIds = new Set(manager.widgets.map((w) => w.id));

		// Remove widgets no longer in manager
		for (const id of currentIds) {
			if (!managerIds.has(id)) {
				unmountWidget(id);
			}
		}

		// Add new widgets from manager
		for (const widget of manager.widgets) {
			if (!currentIds.has(widget.id)) {
				mountWidget(widget);
			}
		}
	});

	onDestroy(() => {
		for (const component of mountedWidgets.values()) {
			unmount(component);
		}
		mountedWidgets.clear();

		if (grid) {
			grid.destroy();
		}
	});
</script>

<div class="grid-stack h-full w-full"></div>
