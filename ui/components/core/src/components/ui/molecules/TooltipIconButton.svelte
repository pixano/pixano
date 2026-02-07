<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { createEventDispatcher } from "svelte";

  import { cn } from "../../../lib/utils/styleUtils";
  import { Button } from "../button";
  import * as Tooltip from "../tooltip";

  export let tooltipContent: string = "";
  export let selected: boolean = false;
  export let disabled: boolean = false;
  export let redconfirm: boolean = false;
  export let big: boolean = false;

  let redConfirmState = false; // Internal state for double confirmation
  const dispatch = createEventDispatcher();

  function handleClick(event: Event) {
    if (redconfirm && !redConfirmState) {
      // First click -> activate confirmation mode (turns red)
      redConfirmState = true;
      event.stopPropagation(); // Prevent immediate action execution
      setTimeout(() => (redConfirmState = false), 3000); // Auto-reset after 3s
    } else {
      // Second click OR normal behavior (redconfirm=false) -> propagate event
      redConfirmState = false;
      dispatch("click", event); // Manually trigger original on:click
    }
  }
</script>

<Tooltip.Root>
  <Tooltip.Trigger tabindex={-1} class="relative">
    {#if redConfirmState}
      <div
        class="absolute right-full top-1/2 -translate-y-1/2 mr-2 bg-foreground text-background text-sm px-3 py-1 rounded shadow-lg whitespace-nowrap z-10"
      >
        Click again to confirm suppression
      </div>
    {/if}
    <Button
      {disabled}
      size={big ? "lg" : "icon"}
      class={cn(
        "bg-transparent text-foreground hover:bg-accent transition-all duration-200 relative active:scale-95 rounded-xl",
        {
          "bg-red-500 text-white hover:bg-red-600": redConfirmState,
          "bg-primary text-primary-foreground shadow-sm": selected,
        },
      )}
      on:click={handleClick}
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
