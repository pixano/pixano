<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  /* eslint-disable svelte/valid-compile */
  import type { Snippet } from "svelte";
  import type { HTMLAttributes } from "svelte/elements";

  import { cn } from "$lib/utils/styleUtils";

  interface Props extends HTMLAttributes<HTMLDivElement> {
    class?: string;
    children?: Snippet;
  }

  let { class: className = undefined, children, ...restProps }: Props = $props();
</script>

<div class={cn("p-6 pt-0", className)} {...restProps}>
  {@render children?.()}
</div>
