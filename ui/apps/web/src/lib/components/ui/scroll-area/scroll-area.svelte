<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { ScrollArea as ScrollAreaPrimitive } from "bits-ui";
  import type { Snippet } from "svelte";

  import { cn } from "$lib/utils.js";

  interface Props {
    class?: string;
    children?: Snippet;
    [key: string]: any;
  }

  let { class: className, children, ...restProps }: Props = $props();
</script>

<ScrollAreaPrimitive.Root class={cn("relative overflow-hidden", className)} {...restProps}>
  {@render children?.()}
</ScrollAreaPrimitive.Root>
