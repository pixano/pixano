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
  import { Eye, Trash2, Lock, Pencil, ChevronRight } from "lucide-svelte";

  import { cn, IconButton } from "@pixano/core/src";
  import SubItem from "./ObjectTabLabelsSubItem.svelte";

  export let open: boolean = false;
  export let name: string = "Girl";
</script>

<div
  class={cn("flex items-center mt-2 hover:bg-slate-100 rounded justify-between", {
    "hover:bg-slate-100": open,
  })}
>
  <div class="flex items-center">
    <IconButton><Eye class="h-4" /></IconButton>
    <span>{name}</span>
  </div>
  <div class="flex items-center">
    <IconButton><Pencil class="h-4" /></IconButton>
    <IconButton><Lock class="h-4" /></IconButton>
    <IconButton><Trash2 class="h-4" /></IconButton>
    <IconButton on:click={() => (open = !open)}
      ><ChevronRight class={cn("transition", { "rotate-90": open })} /></IconButton
    >
  </div>
</div>
{#if open}
  <SubItem open name="Object 1" />
  <SubItem name="Object 2" />
  <SubItem name="Object 3" />
{/if}
