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
  import { Eye, EyeOff, Trash2, Lock, Pencil, ChevronRight } from "lucide-svelte";
  import IconButton from "@pixano/core/src/lib/components/molecules/TooltipIconButton.svelte";
  import { Checkbox } from "@pixano/core/src/lib/components/ui/checkbox";
  import { cn } from "@pixano/core/src/lib/utils";
  import type { DisplayControl, ItemObject, ObjectProperty } from "@pixano/core";

  import { itemObjects } from "../../lib/stores/stores";
  import { objectSetup } from "../../lib/settings/objectSetting";
  import { toggleObjectDisplayControl } from "../../lib/api/objectsApi";

  export let itemObject: ItemObject;

  let open: boolean = true;

  const handleIconClick = (
    displayControlProperty: keyof DisplayControl,
    value: boolean,
    properties: ("bbox" | "mask")[] = ["bbox", "mask"],
  ) => {
    itemObjects.update((oldObjects) =>
      oldObjects.map((object) => {
        if (displayControlProperty === "editing") {
          object.displayControl = {
            ...object.displayControl,
            editing: false,
          };
        }
        if (object.id === itemObject.id) {
          return toggleObjectDisplayControl(object, displayControlProperty, properties, value);
        }
        return object;
      }),
    );
  };

  const deleteObject = () => {
    itemObjects.update((oldObjects) => oldObjects.filter((object) => object.id !== itemObject.id));
  };

  $: properties = objectSetup
    .map((property) => {
      const value = itemObject.features[property.name]?.value;
      if (typeof value !== "string" && typeof value !== "number" && typeof value !== "boolean") {
        return;
      }
      return {
        ...property,
        label: property.label,
        value: typeof value === "string" ? [value] : value,
      };
    })
    .filter(Boolean) as ObjectProperty[];

  $: isLocked = itemObject.displayControl?.locked || false;
  $: isEditing = itemObject.displayControl?.editing || false;
  $: isVisible = !itemObject.displayControl?.hidden;
  $: boxIsVisible = !itemObject.bbox.displayControl?.hidden;
  $: maskIsVisible = !itemObject.mask?.displayControl?.hidden;
</script>

<div
  class={cn("flex items-center mt-2 hover:bg-gray-100 rounded justify-between", {
    "bg-gray-100": open,
  })}
>
  <div class="flex items-center flex-auto max-w-[50%]">
    <IconButton on:click={() => handleIconClick("hidden", isVisible)}>
      {#if isVisible}
        <Eye class="h-4" />
      {:else}
        <EyeOff class="h-4" />
      {/if}
    </IconButton>
    <div class="rounded-full bg-red-400 border border-red-800 w-3 h-3 mr-2 flex-[0_0_0.75rem]" />
    <span class="truncate w-max flex-auto">{itemObject.id}</span>
  </div>
  <div class="flex items-center">
    <IconButton selected={isEditing} on:click={() => handleIconClick("editing", !isEditing)}
      ><Pencil class="h-4" /></IconButton
    >
    <IconButton selected={isLocked} on:click={() => handleIconClick("locked", !isLocked)}
      ><Lock class="h-4" /></IconButton
    >
    <IconButton on:click={deleteObject}><Trash2 class="h-4" /></IconButton>
    <IconButton on:click={() => (open = !open)}
      ><ChevronRight class={cn("transition", { "rotate-90": open })} /></IconButton
    >
  </div>
</div>
{#if open}
  <div class="pl-5 border-b border-b-gray-600">
    <div class="border-l-4 border-dashed border-red-400 pl-4 pb-4 pt-4 flex flex-col gap-4">
      <div>
        <p class="font-medium pb-1">Display</p>
        <div class="flex flex-col gap-2">
          {#if itemObject.bbox}
            <div>
              <Checkbox
                handleClick={() => handleIconClick("hidden", boxIsVisible, ["bbox"])}
                bind:checked={boxIsVisible}
              />
              <span class="font-medium">Box</span>
            </div>
          {/if}
          {#if itemObject.mask}
            <div>
              <Checkbox
                bind:checked={maskIsVisible}
                handleClick={() => handleIconClick("hidden", maskIsVisible, ["mask"])}
              /> <span class="font-medium">Mask</span>
            </div>
          {/if}
        </div>
      </div>
      <div>
        {#each properties as property}
          {#if !property.value}
            <div>erreur. Merci de vous adresser aux administrateurs</div>
          {/if}
          <p class="font-medium pb-1">{property.label}</p>
          {#if property.type === "checkbox"}
            <Checkbox checked={property.value} disabled />
          {/if}
          {#if property.type === "text"}
            <div class="flex justify-start items-center gap-4">
              {#each property.value as value}
                <p
                  class=" font-light rounded-xl bg-primary-light first-letter:uppercase flex justify-center items-center h-6 py-1 px-3"
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
  </div>
{/if}
