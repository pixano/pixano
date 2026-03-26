<script lang="ts">
	import { GripVertical, X } from 'lucide-svelte';
	import type { WidgetInstance, WidgetExtensionConfig } from '$lib/extensions/types.js';

	interface Props {
		widget: WidgetInstance;
		config: WidgetExtensionConfig;
		onRemove: () => void;
	}

	let { widget, config, onRemove }: Props = $props();

	let WidgetComponent = $derived(config.component);
</script>

<div
	class="grid-stack-item-content flex h-full w-full flex-col overflow-hidden rounded-lg border border-border bg-card"
>
	<div class="flex items-center gap-2 border-b border-border bg-muted/50 px-2 py-1">
		<GripVertical class="grid-stack-handle h-4 w-4 cursor-move text-muted-foreground" />
		<span class="flex-1 truncate text-xs font-medium text-card-foreground">{widget.title}</span>
		<button
			onclick={onRemove}
			class="rounded p-0.5 text-muted-foreground hover:bg-destructive/20 hover:text-destructive"
		>
			<X class="h-3.5 w-3.5" />
		</button>
	</div>

	<div class="flex-1 overflow-hidden">
		{#if WidgetComponent}
			<WidgetComponent widgetId={widget.id} options={widget.options} data={widget.data} />
		{/if}
	</div>
</div>
