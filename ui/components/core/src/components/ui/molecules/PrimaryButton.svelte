<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { cn } from "../../../lib/utils/styleUtils";
  import Button from "../button/button.svelte";

  export let isSelected: boolean = false;
  export let disabled: boolean = false;
  export let brighter: boolean = false;
</script>

<Button
  {disabled}
  class={cn("font-medium h-10 px-6 border rounded-full transition-colors flex gap-2 ", {
    "bg-primary hover:bg-primary/80 border-primary text-primary-foreground":
      isSelected,
    "bg-card border-border text-foreground hover:bg-accent": !isSelected,
  })}
  on:click
>
  <slot />
  {#if brighter}
    <span class="relative flex size-3">
      <span
        class="absolute inline-flex h-full w-full animate-ping rounded-full bg-primary opacity-75"
      ></span>
      <span class="relative inline-flex size-3 rounded-full bg-primary"></span>
    </span>
  {/if}
</Button>
