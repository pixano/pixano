<script lang="ts">
	import { Lock, Unlock, PanelRight } from 'lucide-svelte';
	import type { WorkspaceManager } from '$lib/workspace/workspaceManager.svelte.js';
	import type { PanelState } from '$lib/components/ui/resizable-panel/PanelState.svelte.js';

	interface Props {
		manager: WorkspaceManager;
		rightPanel: PanelState;
	}

	let { manager, rightPanel }: Props = $props();

	function toggleEditMode() {
		manager.editMode = !manager.editMode;
	}
</script>

<header
	class="bg-background/80 sticky top-0 z-10 flex h-10 shrink-0 items-center gap-2 border-b border-border px-3 backdrop-blur-sm"
>
	<div class="flex flex-1 items-center gap-3">
		<span class="text-sm font-medium text-foreground">Workspace</span>
		<span class="text-xs text-muted-foreground">— {manager.presetName}</span>
	</div>

	<div class="flex items-center gap-1.5">
		<span class="mr-1 text-xs text-muted-foreground">
			{manager.widgetCount} widget{manager.widgetCount !== 1 ? 's' : ''}
		</span>

		<button
			onclick={toggleEditMode}
			class="flex items-center gap-1.5 rounded-md border border-border px-2.5 py-1 text-xs transition-colors {manager.editMode
				? 'bg-accent text-accent-foreground'
				: 'text-muted-foreground hover:bg-accent/50'}"
		>
			{#if manager.editMode}
				<Unlock class="h-3.5 w-3.5" />
				<span>Edit</span>
			{:else}
				<Lock class="h-3.5 w-3.5" />
				<span>Locked</span>
			{/if}
		</button>

		<button
			onclick={() => rightPanel.toggle()}
			class="flex items-center justify-center rounded-md border border-border p-1 text-xs transition-colors
				{rightPanel.collapsed
				? 'text-muted-foreground hover:bg-accent/50'
				: 'bg-accent text-accent-foreground'}"
			title="Toggle right panel"
		>
			<PanelRight class="h-3.5 w-3.5" />
		</button>
	</div>
</header>
