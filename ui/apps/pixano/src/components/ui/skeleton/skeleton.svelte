<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import type { HTMLAttributes } from "svelte/elements";

  import { cn } from "$lib/utils/styleUtils";

  interface Props extends HTMLAttributes<HTMLDivElement> {
    class?: string;
  }

  let { class: className = undefined, ...restProps }: Props = $props();
</script>

<div class={cn("animate-pulse rounded-md bg-muted/60", className)} {...restProps}></div>
