<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import type { Snippet } from "svelte";

  import { cn } from "$lib/ui";

  interface Props {
    class?: string | undefined | null;
    timeTrack?: Snippet;
  }

  let { class: className = undefined, timeTrack }: Props = $props();
</script>

<div class={cn("flex px-4", className)}>
  <div class={cn("w-full sticky top-0 bg-card z-20")}>
    {@render timeTrack?.()}
  </div>
</div>
