<script lang="ts">
	import * as Sidebar from '$lib/components/ui/sidebar/index.js';
	import { LayoutGrid, FolderOpen } from 'lucide-svelte';
	import WidgetPalette from './WidgetPalette.svelte';
	import type { WidgetRegistry } from '$lib/extensions/WidgetRegistry.js';
	import type { WorkspaceManager } from '$lib/workspace/workspaceManager.svelte.js';

	interface Props {
		registry: WidgetRegistry;
		manager: WorkspaceManager;
	}

	let { registry, manager }: Props = $props();

	let activeSection = $state<'widgets' | 'explorer'>('widgets');

	function handleWidgetAdd(extensionName: string) {
		manager.addWidget(extensionName);
	}
</script>

<Sidebar.Root collapsible="icon" class="border-r border-sidebar-border">
	<Sidebar.Header>
		<div class="flex items-center gap-2 px-2 py-1">
			<div class="flex h-7 w-7 items-center justify-center rounded-md bg-sidebar-primary">
				<span class="text-xs font-bold text-sidebar-primary-foreground">P</span>
			</div>
			<span class="text-sm font-semibold text-sidebar-foreground group-data-[collapsible=icon]:hidden"
				>Pixano</span
			>
		</div>
	</Sidebar.Header>

	<Sidebar.Content>
		<Sidebar.Group>
			<Sidebar.GroupContent>
				<Sidebar.Menu>
					<Sidebar.MenuItem>
						<Sidebar.MenuButton
							isActive={activeSection === 'widgets'}
							onclick={() => (activeSection = 'widgets')}
						>
							<LayoutGrid class="h-4 w-4" />
							<span>Widgets</span>
						</Sidebar.MenuButton>
					</Sidebar.MenuItem>
					<Sidebar.MenuItem>
						<Sidebar.MenuButton
							isActive={activeSection === 'explorer'}
							onclick={() => (activeSection = 'explorer')}
						>
							<FolderOpen class="h-4 w-4" />
							<span>Explorer</span>
						</Sidebar.MenuButton>
					</Sidebar.MenuItem>
				</Sidebar.Menu>
			</Sidebar.GroupContent>
		</Sidebar.Group>

		<Sidebar.Separator />

		<Sidebar.Group class="group-data-[collapsible=icon]:hidden">
			<Sidebar.GroupContent>
				{#if activeSection === 'widgets'}
					<WidgetPalette {registry} onWidgetAdd={handleWidgetAdd} />
				{:else}
					<div class="p-3 text-xs text-muted-foreground">
						Project explorer coming soon...
					</div>
				{/if}
			</Sidebar.GroupContent>
		</Sidebar.Group>
	</Sidebar.Content>

	<Sidebar.Footer>
		<div class="px-2 py-1 text-xs text-muted-foreground group-data-[collapsible=icon]:hidden">
			Pixano v2.0
		</div>
	</Sidebar.Footer>
</Sidebar.Root>
