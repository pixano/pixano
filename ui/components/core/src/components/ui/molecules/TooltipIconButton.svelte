<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { cn } from "../../../lib/utils/styleUtils";
  import { Button } from "../button";
  import * as Tooltip from "../tooltip";

  export let tooltipContent: string = "";
  export let selected: boolean = false;
  export let disabled: boolean = false;
</script>

<Tooltip.Root>
  <Tooltip.Trigger tabindex={-1}>
    <Button
      {disabled}
      size="icon"
      class={cn("bg-transparent text-slate-800 hover:bg-primary-light relative", {
        "bg-primary text-white": selected,
      })}
      on:click
      on:mouseover
    >
      <slot />
    </Button>
  </Tooltip.Trigger>
  {#if tooltipContent}
    <Tooltip.Content>
      <p>{tooltipContent}</p>
    </Tooltip.Content>
  {/if}
</Tooltip.Root>
