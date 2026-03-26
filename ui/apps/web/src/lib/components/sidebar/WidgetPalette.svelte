<script lang="ts">
	import { Image, FileText, Box } from 'lucide-svelte';
	import type { WidgetRegistry } from '$lib/extensions/WidgetRegistry.js';
	import type { WidgetExtensionConfig } from '$lib/extensions/types.js';

	interface Props {
		registry: WidgetRegistry;
		onWidgetAdd?: (extensionName: string) => void;
	}

	let { registry, onWidgetAdd }: Props = $props();

	let extensions = $derived(registry.getAll());

	const iconMap: Record<string, typeof Image> = {
		image: Image,
		'file-text': FileText,
		box: Box
	};

	function getIcon(iconName: string) {
		return iconMap[iconName] ?? Box;
	}
</script>

<div class="flex flex-col gap-2 p-3">
	<h3 class="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Widgets</h3>

	<div class="flex flex-col gap-1.5">
		{#each extensions as ext (ext.name)}
			{@const Icon = getIcon(ext.icon)}
			<button
				class="sidebar-draggable flex items-center gap-3 rounded-md border border-border bg-card px-3 py-2 text-left text-sm text-card-foreground transition-colors hover:bg-accent hover:text-accent-foreground"
				data-extension-name={ext.name}
				onclick={() => onWidgetAdd?.(ext.name)}
			>
				<Icon class="h-4 w-4 text-muted-foreground" />
				<div>
					<div class="text-sm font-medium">{ext.label}</div>
					<div class="text-xs text-muted-foreground">{ext.name}</div>
				</div>
			</button>
		{/each}
	</div>
</div>
