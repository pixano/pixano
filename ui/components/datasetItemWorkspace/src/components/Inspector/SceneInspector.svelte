<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // External library imports

  // Internal library imports
  import { Pencil } from "lucide-svelte";
  import { onDestroy } from "svelte";
  import RangeSlider from "svelte-range-slider-pips";

  import { Image, SequenceFrame, View, type SaveItem } from "@pixano/core";
  import { IconButton, Switch } from "@pixano/core/src";

  import { datasetSchema } from "../../../../../apps/pixano/src/lib/stores/datasetStores";
  import { createFeature } from "../../lib/api/featuresApi";
  import { addOrUpdateSaveItem } from "../../lib/api/objectsApi";
  // Local imports
  import {
    filters,
    imageSmoothing,
    itemMetas,
    mediaViews,
    saveData,
  } from "../../lib/stores/datasetItemWorkspaceStores";
  import { currentFrameIndex } from "../../lib/stores/videoViewerStores";
  import type { Feature, ItemsMeta } from "../../lib/types/datasetItemWorkspaceTypes";
  import UpdateFeatureInputs from "../Features/UpdateFeatureInputs.svelte";

  type ViewMeta = {
    url: string | undefined;
    width: number;
    height: number;
    format: string;
    id: string;
    view: string;
  };

  // Component state variables
  let features: Feature[] = [];
  let isEditing: boolean = false;
  let isVideo: boolean = false;
  let combineChannels: boolean = false;
  let viewMeta: ViewMeta[] = [];

  $: unsubscriberMediaViews = mediaViews.subscribe((views) => {
    viewMeta = Object.values(views || {}).map((view: View | View[]) => {
      let image: Image | SequenceFrame;
      if (Array.isArray(view)) {
        isVideo = true;
        image = view[$currentFrameIndex] as SequenceFrame;
      } else {
        image = view as Image;
      }
      return image
        ? {
            url: image.data.url,
            width: image.data.width,
            height: image.data.height,
            format: image.data.format,
            id: image.id,
            view: image.table_info.name,
          }
        : {
            url: undefined,
            width: 0,
            height: 0,
            format: "",
            id: "",
            view: "",
          };
    });
    features = createFeature($itemMetas.item, $datasetSchema);
  });

  onDestroy(() => {
    unsubscriberMediaViews();
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
      newMetas.item.data[propertyName] = value;
      const save_item: SaveItem = {
        change_type: "update",
        object: newMetas.item,
      };
      saveData.update((current_sd) => addOrUpdateSaveItem(current_sd, save_item));
      return newMetas;
    });
    features = createFeature($itemMetas.item, $datasetSchema);
  };
</script>

<!-- Features Section -->
<div class="p-4 pb-8 text-slate-800">
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
  <h3 class="uppercase font-medium h-10 flex items-center">Views</h3>
  {#each viewMeta as meta}
    <h2 class="font-medium h-10 flex items-center truncate" title="{meta.id} ({meta.view})">
      {meta.id} ({meta.view})
    </h2>
    <div class="mx-4">
      <div class="grid gap-4 grid-cols-[150px_auto]">
        <p class="font-medium">URL</p>
        <p class="truncate" title={meta.url}>{meta.url}</p>
      </div>
      <div class="grid gap-4 grid-cols-[150px_auto]">
        <p class="font-medium">Width</p>
        <p>{meta.width}</p>
      </div>
      <div class="grid gap-4 grid-cols-[150px_auto]">
        <p class="font-medium">Height</p>
        <p>{meta.height}</p>
      </div>
      <div class="grid gap-4 grid-cols-[150px_auto]">
        <p class="font-medium">Format</p>
        <p>{meta.format}</p>
      </div>
    </div>
  {/each}
</div>

<!-- Filters Section -->
<div class="p-4 pb-8 text-slate-800 font-medium">
  <h3 class="uppercase font-medium h-10">FILTERS</h3>

  <!-- General Filters -->
  <div class="border border-gray-300 rounded py-2 px-4 text-sm">
    <h4 class="uppercase font-medium h-6 text-gray-500">GENERAL</h4>
    <!-- Image Smoothing -->
    <div class="w-full my-1 flex items-center justify-between">
      <label for="smoothing" class="select-none cursor-pointer">Image smoothing</label>
      <Switch id="smoothing" bind:checked={$imageSmoothing} onChange={() => {}}></Switch>
    </div>

    {#if !isVideo}
      <!-- Histogram Equalizer -->
      <div class="w-full my-1 flex items-center justify-between">
        <label for="equalizer" class="select-none cursor-pointer">Equalize histogram</label>
        <Switch id="equalizer" bind:checked={$filters.equalizeHistogram} onChange={() => {}} />
      </div>
      <!-- Brightness -->
      <div class="flex items-center">
        <label for="brightness" class="w-20 pb-1">Brightness</label>
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
        <label for="contrast" class="w-20 pb-1">Contrast</label>
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
        <span class="w-8">{Math.round($filters.contrast + 50)}%</span>
      </div>
    {/if}
  </div>

  {#if !isVideo}
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
          <span class="text-left w-4">G</span>
          <span class="w-8">{$filters.redRange[0]}</span>
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
          <span class="w-8">{$filters.redRange[1]}</span>
        </div>
      {:else}
        <!-- Red -->
        <div class="flex items-center text-sm text-center text-red-500">
          <span class="text-left w-4">R</span>
          <span class="w-8">{$filters.redRange[0]}</span>
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
          <span class="w-8">{$filters.redRange[1]}</span>
        </div>

        <!-- Green -->
        <div class="flex items-center text-sm text-center text-green-500">
          <span class="text-left w-4">G</span>
          <span class="w-8">{$filters.greenRange[0]}</span>
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
          <span class="w-8">{$filters.greenRange[1]}</span>
        </div>

        <!-- Blue -->
        <div class="flex items-center text-sm text-center text-blue-500">
          <span class="text-left w-4">B</span>
          <span class="w-8">{$filters.blueRange[0]}</span>
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
          <span class="w-8">{$filters.blueRange[1]}</span>
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
