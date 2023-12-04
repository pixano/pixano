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
  import IconButton from "@pixano/core/src/lib/components/molecules/TooltipIconButton.svelte";
  import { Checkbox } from "@pixano/core/src/lib/components/ui/checkbox";
  import { cn } from "@pixano/core/src/lib/utils";
  import type { ObjectContent, ObjectProperty } from "@pixano/core";

  import { objectSetup } from "../../lib/settings/objectSetting";
  import { objects } from "../../lib/stores/stores";

  export let objectContent: ObjectContent;

  let open: boolean = true;

  const handleEditIconClick = () => {
    objects.update((oldObjects) =>
      oldObjects.map((o) => {
        if (o.id === objectContent.id && o.type === "box") {
          o.boundingBox.editing = !o.boundingBox.editing;
        }
        return o;
      }),
    );
  };

  const handleLockIconClick = () => {
    objects.update((oldObjects) =>
      oldObjects.map((o) => {
        if (o.id === objectContent.id && o.type === "box") {
          o.boundingBox.locked = !o.boundingBox.locked;
        }
        return o;
      }),
    );
  };

  $: properties = Object.entries(objectContent.properties).map(([label, value]) => ({
    label,
    value,
    ...objectSetup.find((p) => p.label === label),
  })) as ObjectProperty[];

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
      {#each properties as property}
        {#if !property.value}
          <div>erreur. Merci de vous adresser aux administrateurs</div>
        {/if}
        <p class="font-medium">{property.label}</p>
        {#if property.type === "checkbox"}
          <Checkbox checked={property.value} />
        {/if}
        {#if property.type === "text"}
          <div class="flex justify-start items-center gap-4">
            {#each property.value as value}
              <p
                class="rounded-xl bg-primary-light first-letter:uppercase flex justify-center items-center h-6 p-1"
              >
                {value}
              </p>
            {/each}
          </div>
        {/if}
        {#if property.type === "number"}
          <span class="rounded-full bg-primary-light h-5 w-5 flex justify-center items-center">
            {property.value}
          </span>
        {/if}
      {/each}
    </div>
  </div>
{/if}
