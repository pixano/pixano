<script lang="ts">
	import { ScrollArea as ScrollAreaPrimitive } from 'bits-ui';
	import { cn } from '$lib/utils.js';

	interface Props {
		class?: string;
		[key: string]: any;
	}

	let { class: className, ...restProps }: Props = $props();
</script>

<ScrollAreaPrimitive.Thumb
	class={cn('relative flex-1 rounded-full bg-border', className)}
	{...restProps}
/>