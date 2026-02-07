<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { cn } from "@pixano/core";

  let className: string | undefined | null = undefined;

  export { className as class };
</script>

<div class={cn("flex px-4", className)}>
  <div class={cn("w-full sticky top-0 bg-card z-20")}>
    <slot name="timeTrack" />
  </div>
</div>
