<script lang="ts">
	import ActivityBar from './ActivityBar.svelte';
	import Toolbar from './Toolbar.svelte';
	import StatusBar from './StatusBar.svelte';
	import LeftPanel from './LeftPanel.svelte';
	import RightPanel from './RightPanel.svelte';
	import { ResizablePanel, PanelState } from '$lib/components/ui/resizable-panel/index.js';
	import GridWorkspace from '$lib/components/grid/GridWorkspace.svelte';
	import { createDefaultRegistry } from '$lib/extensions/builtin/index.js';
	import { WorkspaceManager } from '$lib/workspace/workspaceManager.svelte.js';
	import { DEFAULT_PRESET } from '$lib/workspace/presets.js';

	const registry = createDefaultRegistry();
	const manager = new WorkspaceManager(registry);
	manager.applyPreset(DEFAULT_PRESET);

	const leftPanel = new PanelState({ defaultWidth: 260, minWidth: 200, maxWidth: 480 });
	const rightPanel = new PanelState({ defaultWidth: 300, minWidth: 240, maxWidth: 520 });

	let activeSection = $state('widgets');

	function handleSectionChange(section: string) {
		if (activeSection === section) {
			leftPanel.toggle();
		} else {
			activeSection = section;
			if (leftPanel.collapsed) leftPanel.collapsed = false;
		}
	}
</script>

<div class="flex h-screen flex-col bg-background text-foreground">
	<Toolbar {manager} {rightPanel} />
	<div class="flex flex-1 overflow-hidden">
		<ActivityBar {activeSection} onSectionChange={handleSectionChange} />
		<ResizablePanel state={leftPanel} side="left">
			<LeftPanel {activeSection} {registry} {manager} />
		</ResizablePanel>
		<div class="flex-1 overflow-hidden">
			<GridWorkspace {manager} {registry} />
		</div>
		<ResizablePanel state={rightPanel} side="right">
			<RightPanel {manager} />
		</ResizablePanel>
	</div>
	<StatusBar {manager} />
</div>
