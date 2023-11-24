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
  import { Eye, ChevronRight, PlusCircle } from "lucide-svelte";
  import IconButton from "@pixano/core/src/lib/components/molecules/TooltipIconButton.svelte";
  import { cn } from "@pixano/core/src/lib/utils";
  import ArrowSvg from "./ArrowSvg.svelte";

  export let open: boolean = false;
  export let name: string = "Object 1";
</script>

<div class="flex pl-4 mt-2 w-full">
  <div class="pt-4">
    <div class="rounded-full bg-red-400 border border-red-800 w-3 h-3 mr-2" />
    <div class={cn({ "border-l-2 ml-[5px] border-dashed border-red-400 h-full w-1": open })} />
  </div>
  <div class="flex flex-col gap-2 w-full">
    <div class="flex justify-between w-full items-center">
      <span>{name}</span>
      <IconButton on:click={() => (open = !open)}
        ><ChevronRight class={cn("transition", { "rotate-90": open })} /></IconButton
      >
    </div>
    {#if open}
      <div class="flex">
        <Eye />
        <div class="ml-4 flex flex-col gap-2">
          <p class="font-medium">Box</p>
          <p class="font-light">B002324</p>
          <p class="font-medium">Mask</p>
          <p class="font-light">M002324</p>
        </div>
      </div>
      <span>Action</span>
      <div class="flex items-center gap-4">
        <span class="rounded border border-primary px-2 py-1">Touch</span>
        <ArrowSvg />
        <span class="rounded border border-primary px-2 py-1">Object 7</span>
        <IconButton><PlusCircle class="w-8 h-8" strokeWidth={1} /></IconButton>
      </div>
    {/if}
  </div>
</div>
