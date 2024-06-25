<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { Button } from "../button";
  import * as Tooltip from "../tooltip";
  import { cn } from "../../../lib/utils/styleUtils";

  export let tooltipContent: string = "";
  export let selected: boolean = false;
</script>

<Tooltip.Root>
  <Tooltip.Trigger tabindex={-1}>
    <Button
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
