<script lang="ts">
  /**
   * @copyright CEA
   * @author CEA
   * @license CECILL
   *
   * This software is a collaborative computer program whose purpose is to
   * generate and explore labeled data for computer vision applications.
   * This software is governed by the CeCILL-C license under French law and
   * abiding by the rules of distribution of free software. You can use,
   * modify and/ or redistribute the software under the terms of the CeCILL-C
   * license as circulated by CEA, CNRS and INRIA at the following URL
   *
   * http://www.cecill.info
   */

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
      class={cn("bg-transparent text-gray-800 hover:bg-primary-light relative", {
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
