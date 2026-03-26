<script lang="ts">
	import type { WorkspaceManager } from '$lib/workspace/workspaceManager.svelte.js';

	interface Props {
		manager: WorkspaceManager;
	}

	let { manager }: Props = $props();
</script>

<footer class="flex items-center justify-between border-t border-border bg-muted/30 px-3 py-1">
	<div class="flex items-center gap-3 text-xs text-muted-foreground">
		<span>{manager.widgetCount} widget{manager.widgetCount !== 1 ? 's' : ''}</span>
		<span>·</span>
		<span>{manager.presetName}</span>
	</div>

	<div class="flex items-center gap-3 text-xs text-muted-foreground">
		<span>{manager.editMode ? 'Edit Mode' : 'View Mode'}</span>
	</div>
</footer>
