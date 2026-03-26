<script lang="ts">
	import { ScrollArea as ScrollAreaPrimitive } from 'bits-ui';
	import { cn } from '$lib/utils.js';
	import type { Snippet } from 'svelte';

	interface Props {
		class?: string;
		children?: Snippet;
		orientation?: 'vertical' | 'horizontal';
		[key: string]: any;
	}

	let { class: className, children, orientation = 'vertical', ...restProps }: Props = $props();
</script>

<ScrollAreaPrimitive.Scrollbar
	{orientation}
	class={cn(
		'flex touch-none select-none transition-colors',
		orientation === 'vertical' && 'h-full w-2.5 border-l border-l-transparent p-[1px]',
		orientation === 'horizontal' && 'h-2.5 flex-col border-t border-t-transparent p-[1px]',
		className
	)}
	{...restProps}
>
	{@render children?.()}
</ScrollAreaPrimitive.Scrollbar>