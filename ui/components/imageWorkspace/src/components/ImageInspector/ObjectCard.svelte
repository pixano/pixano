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
  import { Eye, EyeOff, Trash2, Pencil, ChevronRight } from "lucide-svelte";

  import { cn, IconButton, Checkbox } from "@pixano/core/src";
  import type { DisplayControl, ItemObject } from "@pixano/core";

  import { canSave, itemObjects } from "../../lib/stores/imageWorkspaceStores";
  import { createObjectCardId, toggleObjectDisplayControl } from "../../lib/api/objectsApi";
  import { createFeature } from "../../lib/api/featuresApi";

  import ItemFeatures from "../Features/FeatureInputs.svelte";

  export let itemObject: ItemObject;
  export let colorScale: (id: string) => string;

  let color: string;
  let open: boolean = false;
  let showIcons: boolean = false;

  $: features = createFeature(itemObject.features);

  $: {
    color = colorScale(itemObject.id);
  }

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
          object = toggleObjectDisplayControl(object, displayControlProperty, properties, value);
        }
        if (value && itemObject.highlighted === "self") {
          object.highlighted = "all";
        }
        return object;
      }),
    );
  };

  const deleteObject = () => {
    itemObjects.update((oldObjects) => oldObjects.filter((object) => object.id !== itemObject.id));
    canSave.set(true);
  };

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

  const onColoredDotClick = () => {
    const isObjectHighlighted = itemObject.highlighted === "self";
    itemObjects.update((oldObjects) =>
      oldObjects.map((object) => {
        if (isObjectHighlighted) {
          object.highlighted = "all";
        } else if (object.id === itemObject.id) {
          object.highlighted = "self";
        } else {
          object.highlighted = "none";
        }
        return object;
      }),
    );
  };
</script>

<article
  on:mouseenter={() => (showIcons = true)}
  on:mouseleave={() => (showIcons = open)}
  id={createObjectCardId(itemObject)}
>
  <div
    class={cn("flex items-center mt-1  rounded justify-between text-slate-800 bg-white border-2 ")}
    style="border-color:{itemObject.highlighted === 'self' ? color : 'transparent'}"
  >
    <div class="flex items-center flex-auto max-w-[50%]">
      <IconButton
        on:click={() => handleIconClick("hidden", isVisible)}
        tooltipContent={isVisible ? "Hide" : "Show"}
      >
        {#if isVisible}
          <Eye class="h-4" />
        {:else}
          <EyeOff class="h-4" />
        {/if}
      </IconButton>
      <button
        class="rounded-full border w-3 h-3 mr-2 flex-[0_0_0.75rem]"
        style="background:{color}"
        on:click={onColoredDotClick}
      />
      <span class="truncate w-max flex-auto">{itemObject.id}</span>
    </div>
    <div class="flex items-center">
      {#if showIcons || isEditing}
        <IconButton
          tooltipContent="Edit object"
          selected={isEditing}
          on:click={() => {
            handleIconClick("editing", !isEditing), (open = true);
          }}><Pencil class="h-4" /></IconButton
        >
        <IconButton tooltipContent="Delete object" on:click={deleteObject}
          ><Trash2 class="h-4" /></IconButton
        >
      {/if}
      <IconButton
        on:click={() => (open = !open)}
        tooltipContent={open ? "Hide features" : "Show features"}
      >
        <ChevronRight class={cn("transition", { "rotate-90": open })} strokeWidth={1} />
      </IconButton>
    </div>
  </div>
  {#if open}
    <div class="pl-5 border-b border-b-slate-600 text-slate-800 bg-white">
      <div
        class="border-l-4 border-dashed border-red-400 pl-4 pb-4 pt-4 flex flex-col gap-4"
        style="border-color:{color}"
      >
        <div class="flex flex-col gap-2">
          <div>
            <p class="font-medium first-letter:uppercase">display</p>
            <div class="flex gap-4">
              {#if itemObject.bbox}
                <div class="flex gap-2 mt-2 items-center">
                  <p class="font-light first-letter:uppercase">Box</p>
                  <Checkbox
                    handleClick={() => handleIconClick("hidden", boxIsVisible, ["bbox"])}
                    bind:checked={boxIsVisible}
                    class="mx-1"
                  />
                </div>
              {/if}
              {#if itemObject.mask}
                <div class="flex gap-2 mt-2 items-center">
                  <p class="font-light first-letter:uppercase">Mask</p>
                  <Checkbox
                    handleClick={() => handleIconClick("hidden", maskIsVisible, ["mask"])}
                    bind:checked={maskIsVisible}
                    class="mx-1"
                  />
                </div>
              {/if}
            </div>
          </div>
          <ItemFeatures {features} {isEditing} {saveInputChange} />
        </div>
      </div>
    </div>
  {/if}
</article>
