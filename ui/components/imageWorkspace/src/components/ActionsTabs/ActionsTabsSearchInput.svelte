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
  import { Eye, Filter, Search, EyeOff } from "lucide-svelte";

  import { Input } from "@pixano/core/src/lib/components/ui/input";
  import IconButton from "@pixano/core/src/lib/components/molecules/TooltipIconButton.svelte";

  export let hideAllObjects: boolean = true;
  let tooltipContent: string = hideAllObjects ? "show all" : "hide all";
</script>

<div class="flex mt-4 items-center gap-3">
  <IconButton {tooltipContent} on:click>
    {#if hideAllObjects}
      <EyeOff class="h-4" />
    {:else}
      <Eye class="h-4" />
    {/if}
  </IconButton>
  <IconButton>
    <Filter class="h-4" />
  </IconButton>
  <Input placeholder="Search" class="grow">
    <Search class="h-4" />
  </Input>
</div>
