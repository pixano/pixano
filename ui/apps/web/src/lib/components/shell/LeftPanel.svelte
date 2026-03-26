<script lang="ts">
	import WidgetPalette from '$lib/components/sidebar/WidgetPalette.svelte';
	import type { WidgetRegistry } from '$lib/extensions/WidgetRegistry.js';
	import type { WorkspaceManager } from '$lib/workspace/workspaceManager.svelte.js';
	import { FolderOpen, LayoutGrid, Search } from 'lucide-svelte';

	interface Props {
		activeSection: string;
		registry: WidgetRegistry;
		manager: WorkspaceManager;
	}

	let { activeSection, registry, manager }: Props = $props();

	const sectionLabels: Record<string, { label: string; icon: typeof FolderOpen }> = {
		explorer: { label: 'Explorer', icon: FolderOpen },
		widgets: { label: 'Widgets', icon: LayoutGrid },
		search: { label: 'Search', icon: Search }
	};

	let section = $derived(sectionLabels[activeSection] ?? sectionLabels.widgets);

	function handleWidgetAdd(extensionName: string) {
		manager.addWidget(extensionName);
	}
</script>

<div class="flex h-full flex-col bg-background">
	<!-- Panel header -->
	<div class="flex h-10 items-center gap-2 border-b border-border px-3">
		<section.icon class="h-4 w-4 text-muted-foreground" />
		<span class="text-xs font-semibold uppercase tracking-wider text-foreground">
			{section.label}
		</span>
	</div>

	<!-- Panel content -->
	<div class="flex-1 overflow-y-auto">
		{#if activeSection === 'widgets'}
			<WidgetPalette {registry} onWidgetAdd={handleWidgetAdd} />
		{:else if activeSection === 'explorer'}
			<div class="p-4">
				<div class="flex flex-col gap-3 text-muted-foreground">
					<p class="text-xs">Browse datasets and projects.</p>
					<div class="space-y-1">
						{#each ['COCO 2017', 'ImageNet Val', 'Custom Dataset'] as ds}
							<div
								class="flex items-center gap-2 rounded-md px-2 py-1.5 text-xs hover:bg-accent hover:text-accent-foreground"
							>
								<FolderOpen class="h-3.5 w-3.5" />
								<span>{ds}</span>
							</div>
						{/each}
					</div>
				</div>
			</div>
		{:else if activeSection === 'search'}
			<div class="p-3">
				<input
					type="text"
					placeholder="Search samples..."
					class="w-full rounded-md border border-input bg-muted/50 px-3 py-1.5 text-xs text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring"
				/>
				<p class="mt-3 text-xs text-muted-foreground">
					Type to search across datasets and annotations.
				</p>
			</div>
		{/if}
	</div>
</div>
