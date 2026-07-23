<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import type { Snippet } from "svelte";
  import type { HTMLAttributes } from "svelte/elements";

  import { cn } from "$lib/utils/styleUtils";

  interface Props extends HTMLAttributes<HTMLParagraphElement> {
    class?: string;
    children?: Snippet;
  }

  let { class: className = undefined, children, ...restProps }: Props = $props();
</script>

<p class={cn("text-sm text-muted-foreground", className)} {...restProps}>
  {@render children?.()}
</p>
