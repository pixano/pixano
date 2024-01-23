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

  import { cn, IconButton, Checkbox } from "@pixano/core/src";
  import type { DisplayControl, ItemObject } from "@pixano/core";

  import { canSave, itemObjects } from "../../lib/stores/imageWorkspaceStores";
  import { toggleObjectDisplayControl } from "../../lib/api/objectsApi";
  import { createFeature } from "../../lib/api/featuresApi";

  import ItemFeatures from "../Features/FeatureInputs.svelte";

  export let itemObject: ItemObject;
  export let colorScale: (id: string) => string;

  $: features = createFeature(itemObject.features);

  let color: string;
  $: {
    color = colorScale(itemObject.id);
  }

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
    canSave.set(true);
  };

  $: isLocked = itemObject.displayControl?.locked || false;
  $: isEditing = itemObject.displayControl?.editing || false;
  $: isVisible = !itemObject.displayControl?.hidden;
  $: boxIsVisible = !itemObject.bbox?.displayControl?.hidden;
  $: maskIsVisible = !itemObject.mask?.displayControl?.hidden;

  const saveInputChange = (value: string | boolean | number, propertyName: string) => {
    itemObjects.update((oldObjects) =>
      oldObjects.map((object) => {
        if (object.id === itemObject.id) {
          object.features = {
            ...object.features,
            [propertyName]: {
              ...object.features[propertyName],
              value,
            },
          };
        }
        return object;
      }),
    );
    canSave.set(true);
  };
</script>

<div class={cn("flex items-center mt-1  rounded justify-between text-slate-800 bg-white")}>
  <div class="flex items-center flex-auto max-w-[50%]">
    <IconButton on:click={() => handleIconClick("hidden", isVisible)}>
      {#if isVisible}
        <Eye class="h-4" />
      {:else}
        <EyeOff class="h-4" />
      {/if}
    </IconButton>
    <div class="rounded-full border w-3 h-3 mr-2 flex-[0_0_0.75rem]" style="background:{color}" />
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
  <div class="pl-5 border-b border-b-gray-600 text-slate-800 bg-white">
    <div
      class="border-l-4 border-dashed border-red-400 pl-4 pb-4 pt-4 flex flex-col gap-4"
      style="border-color:{color}"
    >
      <div>
        <p class="font-medium pb-1">Display</p>
        <div class="flex flex-col gap-2">
          {#if itemObject.bbox}
            <div>
              <Checkbox
                handleClick={() => handleIconClick("hidden", boxIsVisible, ["bbox"])}
                bind:checked={boxIsVisible}
              />
              <span class="font-medium">Bounding box</span>
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
        <ItemFeatures {features} {isEditing} {saveInputChange} />
      </div>
    </div>
  </div>
{/if}
