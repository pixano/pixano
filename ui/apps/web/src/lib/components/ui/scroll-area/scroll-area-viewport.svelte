<script lang="ts">
	import { ScrollArea as ScrollAreaPrimitive } from 'bits-ui';
	import { cn } from '$lib/utils.js';
	import type { Snippet } from 'svelte';

	interface Props {
		class?: string;
		children?: Snippet;
		[key: string]: any;
	}

	let { class: className, children, ...restProps }: Props = $props();
</script>

<ScrollAreaPrimitive.Viewport class={cn('h-full w-full rounded-[inherit]', className)} {...restProps}>
	{@render children?.()}
</ScrollAreaPrimitive.Viewport>