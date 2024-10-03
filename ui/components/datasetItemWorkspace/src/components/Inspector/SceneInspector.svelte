<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // External library imports
  import RangeSlider from "svelte-range-slider-pips";

  // Internal library imports
  import { Pencil } from "lucide-svelte";
  import { IconButton, Switch, type ItemFeature } from "@pixano/core/src";
  import { View, Image, SequenceFrame } from "@pixano/core";

  // Local imports
  import {
    canSave,
    itemMetas,
    filters,
    imageSmoothing,
  } from "../../lib/stores/datasetItemWorkspaceStores";
  import UpdateFeatureInputs from "../Features/UpdateFeatureInputs.svelte";
  import { createFeature } from "../../lib/api/featuresApi";
  import type { Feature, ItemsMeta } from "../../lib/types/datasetItemWorkspaceTypes";
  import { defaultSceneFeatures } from "../../lib/settings/defaultFeatures";

  type ItemMeta = {
    fileName: string | undefined;
    width: number;
    height: number;
    format: string;
    id: string;
  };

  // Component state variables
  let features: Feature[] = [];
  let isEditing: boolean = false;
  let itemType: string = "";
  let combineChannels: boolean = false;
  let itemMeta: ItemMeta[] = [];

  itemMetas.subscribe((metas) => {
    itemMeta = Object.values(metas.views || {}).map((view: Image | SequenceFrame[]) => {
      const image: Image = Array.isArray(view) ? view[0] : view;
      itemType = metas.type;
      return {
        fileName: image.data.url.split("/").at(-1),
        width: image.data.width,
        height: image.data.height,
        format: image.data.format,
        id: image.id,
      };
    });
    const mainFeatures: Record<string, ItemFeature> = Object.values(metas.mainFeatures || {}).length
      ? metas.mainFeatures
      : defaultSceneFeatures;
    //features = createFeature(mainFeatures); //XXX TODO
  });

  /**
   * Toggle the editing state.
   */
  const handleEditIconClick = (): void => {
    isEditing = !isEditing;
  };

  /**
   * Update the text input change for a specific property in itemMetas.
   *
   * @param value - The new value for the property.
   * @param propertyName - The name of the property to update.
   */
  const handleTextInputChange = (value: string | boolean | number, propertyName: string) => {
    itemMetas.update((oldMetas) => {
      const newMetas: ItemsMeta = { ...oldMetas };
      newMetas.mainFeatures = {
        ...newMetas.mainFeatures,
        [propertyName]: {
          ...(newMetas.mainFeatures?.[propertyName] || defaultSceneFeatures[propertyName]),
          value,
        },
      };
      return newMetas;
    });
    canSave.set(true);
  };
</script>

<!-- Features Section -->
<div class="border-b-2 border-b-slate-500 p-4 pb-8 text-slate-800">
  <h3 class="uppercase font-medium h-10">
    <span>Features</span>
    <IconButton
      selected={isEditing}
      on:click={handleEditIconClick}
      tooltipContent="Edit scene features"
    >
      <Pencil class="h-4" />
    </IconButton>
  </h3>
  <div class="mx-4">
    <UpdateFeatureInputs
      featureClass="main"
      {features}
      {isEditing}
      saveInputChange={handleTextInputChange}
    />
  </div>
</div>

<!-- Item Meta Information Section -->
<div class="p-4 pb-8 border-b-2 border-b-slate-500 text-slate-800">
  {#each itemMeta as meta}
    <h3 class="uppercase font-medium h-10 flex items-center">{meta.id}</h3>
    <div class="mx-4 mb-4">
      <div class="grid gap-4 grid-cols-[150px_auto] mt-2">
        <p class="font-medium first-letter:uppercase">File name</p>
        <p class="truncate" title={meta.fileName}>{meta.fileName}</p>
      </div>
      <div class="grid gap-4 grid-cols-[150px_auto] mt-2">
        <p class="font-medium first-letter:uppercase">Width</p>
        <p>{meta.width}</p>
      </div>
      <div class="grid gap-4 grid-cols-[150px_auto] mt-2">
        <p class="font-medium first-letter:uppercase">Height</p>
        <p>{meta.height}</p>
      </div>
      <div class="grid gap-4 grid-cols-[150px_auto] mt-2">
        <p class="font-medium first-letter:uppercase">Format</p>
        <p>{meta.format}</p>
      </div>
    </div>
  {/each}
</div>

<!-- Filters Section -->
<div class="p-4 pb-8 border-b-2 border-b-slate-500 text-slate-800 font-medium">
  <h3 class="uppercase font-medium h-10">FILTERS</h3>

  <!-- General Filters -->
  <div class="border border-gray-300 rounded py-2 px-4 text-sm">
    <h4 class="uppercase font-medium h-6 text-gray-500">GENERAL</h4>
    <!-- Image Smoothing -->
    <div class="w-full my-1 flex items-center justify-between">
      <label for="smoothing" class="select-none cursor-pointer"> Image smoothing </label>
      <Switch id="smoothing" bind:checked={$imageSmoothing} onChange={() => {}}></Switch>
    </div>

    {#if itemType === "image"}
      <!-- Histogram Equalizer -->
      <div class="w-full my-1 flex items-center justify-between">
        <label for="equalizer" class="select-none cursor-pointer"> Equalize histogram </label>
        <Switch id="equalizer" bind:checked={$filters.equalizeHistogram} onChange={() => {}} />
      </div>
      <!-- Brightness -->
      <div class="flex items-center">
        <label for="brightness" class="w-20 pb-1">Brightness </label>
        <div class="grow text-xs">
          <RangeSlider
            range="min"
            min={-0.5}
            max={0.5}
            step={0.01}
            values={[$filters.brightness]}
            springValues={{ stiffness: 1, damping: 1 }}
            on:change={(e) => {
              $filters.brightness = e.detail.value;
            }}
          />
        </div>
        <span class="w-8">{Math.round($filters.brightness * 100 + 50)}%</span>
      </div>

      <!-- Contrast -->
      <div class="flex items-center text-sm">
        <label for="contrast" class="w-20 pb-1">Contrast </label>
        <div class="grow text-xs">
          <RangeSlider
            range="min"
            min={-50}
            max={50}
            step={1}
            values={[$filters.contrast]}
            springValues={{ stiffness: 1, damping: 1 }}
            on:change={(e) => {
              $filters.contrast = e.detail.value;
            }}
          />
        </div>
        <span class="w-8">{Math.round($filters.contrast + 50)}% </span>
      </div>
    {/if}
  </div>

  {#if itemType === "image"}
    <!-- Color Channels Filters -->
    <div class="mt-4 border border-gray-300 rounded py-2 px-4 text-sm">
      <h4 class="uppercase font-medium h-6 text-gray-500">CHANNELS</h4>

      {#if $itemMetas.color === "rgba"}
        <div class="w-full my-1 flex items-center justify-between">
          <label for="grayscale" class="select-none cursor-pointer text-sm">
            Combine RGB channels
          </label>
          <Switch id="grayscale" bind:checked={combineChannels} onChange={() => {}} />
        </div>
      {/if}
      {#if combineChannels || $itemMetas.color === "grayscale"}
        <!-- Grayscale -->
        <div class="flex items-center text-sm text-center">
          <span class="text-left w-4"> G </span>
          <span class="w-8"> {$filters.redRange[0]} </span>
          <div class="grow text-xs">
            <RangeSlider
              range
              pushy
              min={0}
              max={255}
              step={1}
              springValues={{ stiffness: 1, damping: 1 }}
              values={$filters.redRange}
              on:change={(e) => {
                $filters.redRange = e.detail.values;
                $filters.blueRange = e.detail.values;
                $filters.greenRange = e.detail.values;
              }}
            />
          </div>
          <span class="w-8"> {$filters.redRange[1]} </span>
        </div>
      {:else}
        <!-- Red -->
        <div class="flex items-center text-sm text-center text-red-500">
          <span class="text-left w-4"> R </span>
          <span class="w-8"> {$filters.redRange[0]} </span>
          <div class="grow text-xs">
            <RangeSlider
              range
              pushy
              min={0}
              max={255}
              step={1}
              springValues={{ stiffness: 1, damping: 1 }}
              values={$filters.redRange}
              on:change={(e) => {
                $filters.redRange = e.detail.values;
              }}
            />
          </div>
          <span class="w-8"> {$filters.redRange[1]} </span>
        </div>

        <!-- Green -->
        <div class="flex items-center text-sm text-center text-green-500">
          <span class="text-left w-4"> G </span>
          <span class="w-8"> {$filters.greenRange[0]} </span>
          <div class="grow text-xs">
            <RangeSlider
              range
              pushy
              min={0}
              max={255}
              step={1}
              springValues={{ stiffness: 1, damping: 1 }}
              values={$filters.greenRange}
              on:change={(e) => {
                $filters.greenRange = e.detail.values;
              }}
            />
          </div>
          <span class="w-8"> {$filters.greenRange[1]} </span>
        </div>

        <!-- Blue -->
        <div class="flex items-center text-sm text-center text-blue-500">
          <span class="text-left w-4"> B </span>
          <span class="w-8"> {$filters.blueRange[0]} </span>
          <div class="grow text-xs">
            <RangeSlider
              range
              pushy
              min={0}
              max={255}
              step={1}
              springValues={{ stiffness: 1, damping: 1 }}
              values={$filters.blueRange}
              on:change={(e) => {
                $filters.blueRange = e.detail.values;
              }}
            />
          </div>
          <span class="w-8"> {$filters.blueRange[1]} </span>
        </div>
      {/if}
    </div>

    <!-- 16-BIT SETTINGS -->
    {#if $itemMetas.format === "16bit"}
      <div class="mt-4 border border-gray-300 rounded py-2 px-4 text-sm">
        <h4 class="uppercase font-medium h-6 text-gray-500">16-BIT SETTINGS</h4>
        <div class="my-1">Select range :</div>
        <div class="flex items-center text-sm text-center">
          <input
            type="number"
            class="w-16 bg-inherit outline-none text-center"
            bind:value={$filters.u16BitRange[0]}
          />
          <div class="grow text-xs">
            <RangeSlider
              range
              pushy
              min={0}
              max={65535}
              step={1}
              springValues={{ stiffness: 1, damping: 1 }}
              bind:values={$filters.u16BitRange}
            />
          </div>
          <input
            type="number"
            class="w-16 bg-inherit outline-none text-center"
            bind:value={$filters.u16BitRange[1]}
          />
        </div>
      </div>
    {/if}
  {/if}
</div>
