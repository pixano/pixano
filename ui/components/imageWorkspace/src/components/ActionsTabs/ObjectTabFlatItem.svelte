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
  import { Eye, Trash2, Lock, Pencil, ChevronRight, PlusCircle } from "lucide-svelte";
  import IconButton from "@pixano/core/src/lib/components/molecules/TooltipIconButton.svelte";
  import { Checkbox } from "@pixano/core/src/lib/components/ui/checkbox";
  import { cn } from "@pixano/core/src/lib/utils";
  import ArrowSvg from "./ArrowSvg.svelte";
  import type { ObjectContent } from "../../lib/types/objects";

  export let objectContent: ObjectContent;

  let open: boolean = true;
  let boxChecked: boolean = objectContent.type === "box";
  let maskChecked: boolean = objectContent.type === "mask";

  const handleEditIconClick = () => {
    if (objectContent.type === "box") {
      objectContent.boundingBox.editing = !objectContent.boundingBox.editing;
    }
  };

  const handleLockIconClick = () => {
    if (objectContent.type === "box") {
      objectContent.boundingBox.locked = !objectContent.boundingBox.locked;
    }
  };

  $: isEditing = objectContent.type === "box" && objectContent.boundingBox.editing;
  $: isLocked = objectContent.type === "box" && objectContent.boundingBox.locked;
</script>

<div
  class={cn("flex items-center mt-2 hover:bg-gray-100 rounded justify-between", {
    "bg-gray-100": open,
  })}
>
  <div class="flex items-center">
    <IconButton><Eye class="h-4" /></IconButton>
    <div class="rounded-full bg-red-400 border border-red-800 w-3 h-3 mr-2" />
    <span>{objectContent.name}</span>
  </div>
  <div class="flex items-center">
    <IconButton selected={isEditing} on:click={handleEditIconClick}
      ><Pencil class="h-4" /></IconButton
    >
    <IconButton selected={isLocked} on:click={handleLockIconClick}><Lock class="h-4" /></IconButton>
    <IconButton><Trash2 class="h-4" /></IconButton>
    <IconButton on:click={() => (open = !open)}
      ><ChevronRight class={cn("transition", { "rotate-90": open })} /></IconButton
    >
  </div>
</div>
{#if open}
  <div class="pl-5 border-b border-b-gray-600">
    <div class="border-l-4 border-dashed border-red-400 pl-4 pb-4 pt-4">
      <p class="font-medium mb-4">Display</p>
      <div class="my-2 flex flex-col gap-4 mb-4">
        <span>
          <Checkbox bind:checked={boxChecked} /> Box
        </span>
        <span>
          <Checkbox bind:checked={maskChecked} /> Mask
        </span>
      </div>
      <p class="font-medium">Label</p>
      <div class="my-2 flex gap-3 items-center">
        <div
          class="flex items-center rounded-2xl bg-primary-light py-1 px-4 first-letter:uppercase w-fit h-fit"
        >
          Girl
        </div>
        <IconButton><PlusCircle class="w-8 h-8" strokeWidth={1} /></IconButton>
      </div>
      <p class="font-medium">Action</p>
      <div class="flex items-center gap-4">
        <span class="rounded border border-primary px-2 py-1">Touch</span>
        <ArrowSvg />
        <span class="rounded border border-primary px-2 py-1">Object 7</span>
        <IconButton><PlusCircle class="w-8 h-8" strokeWidth={1} /></IconButton>
      </div>
    </div>
  </div>
{/if}
