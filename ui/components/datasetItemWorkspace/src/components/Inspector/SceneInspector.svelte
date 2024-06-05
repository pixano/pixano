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

  import { Pencil } from "lucide-svelte";
  import RangeSlider from "svelte-range-slider-pips";

  import { IconButton, type ItemView } from "@pixano/core/src";

  import { canSave, itemMetas, filters } from "../../lib/stores/datasetItemWorkspaceStores";
  import UpdateFeatureInputs from "../Features/UpdateFeatureInputs.svelte";

  import { createFeature } from "../../lib/api/featuresApi";
  import type { Feature } from "../../lib/types/datasetItemWorkspaceTypes";
  import { defaultSceneFeatures } from "../../lib/settings/defaultFeatures";

  type ItemMeta = {
    fileName: string;
    width: number;
    height: number;
    format: string;
    id: string;
  };

  let features: Feature[];
  let itemMeta: ItemMeta[] = [];
  let isEditing: boolean = false;
  let itemType: string;

  itemMetas.subscribe((metas) => {
    itemMeta = Object.values(metas.views).map((view: ItemView | ItemView[]) => {
      const image: ItemView = Array.isArray(view) ? view[0] : view;
      itemType = metas.type;
      return {
        fileName: image.uri.split("/").at(-1) as string,
        width: image.features.width.value as number,
        height: image.features.height.value as number,
        format: image.uri.split(".").at(-1)?.toUpperCase() as string,
        id: image.id,
      };
    });
    const mainFeatures = Object.values(metas.mainFeatures).length
      ? metas.mainFeatures
      : defaultSceneFeatures;
    features = createFeature(mainFeatures);
  });

  const handleEditIconClick = () => {
    isEditing = !isEditing;
  };

  const handleTextInputChange = (value: string | boolean | number, propertyName: string) => {
    itemMetas.update((oldMetas) => {
      const newMetas = { ...oldMetas };
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

{#if itemType === "image"}
  <!-- FILTERS -->
  <div class="p-4 pb-8 border-b-2 border-b-slate-500 text-slate-800 font-medium">
    <h3 class="uppercase font-medium h-10">FILTERS</h3>
    <div class="mb-4">
      <label for="brightness">Brightness : {Math.round($filters.brightness * 100 + 50)}%</label>
      <input
        type="range"
        id="brightness"
        min="-0.5"
        max="0.5"
        step="0.01"
        class="w-full mt-1 cursor-pointer accent-primary"
        bind:value={$filters.brightness}
      />

      <label for="contrast">Contrast : {Math.round($filters.contrast + 50)}%</label>
      <input
        type="range"
        id="contrast"
        min="-50"
        max="50"
        step="1"
        class="w-full mt-1 cursor-pointer accent-primary"
        bind:value={$filters.contrast}
      />
      
      <div class="pt-2 flex items-center space-x-2">
        <input
          type="checkbox"
          id="equalizer"
          class="cursor-pointer w-4 h-4"
          bind:checked={$filters.equalizeHistogram}
        />
        <label for="equalizer" class="select-none cursor-pointer"> Equalize histogram </label>
      </div>

      <!-- Color ranges -->
      <div class="pt-4">Color ranges :</div>
      <!-- Red -->
      <div class="flex items-center text-sm text-center text-red-500">
        <span class="text-left w-6"> R : </span>
        <span class="w-8"> {$filters.redRange[0]} </span>
        <div class="grow">
          <RangeSlider min={0} max={255} step={1} bind:values={$filters.redRange} />
        </div>
        <span class="w-8"> {$filters.redRange[1]} </span>
      </div>

      <!-- Green -->
      <div class="flex items-center text-sm text-center text-green-500">
        <span class="text-left w-6"> G : </span>
        <span class="w-8"> {$filters.greenRange[0]} </span>
        <div class="grow">
          <RangeSlider min={0} max={255} step={1} bind:values={$filters.greenRange} />
        </div>
        <span class="w-8"> {$filters.greenRange[1]} </span>
      </div>

      <!-- Blue -->
      <div class="flex items-center text-sm text-center text-blue-500">
        <span class="text-left w-6"> B : </span>
        <span class="w-8"> {$filters.blueRange[0]} </span>
        <div class="grow">
          <RangeSlider min={0} max={255} step={1} bind:values={$filters.blueRange} />
        </div>
        <span class="w-8"> {$filters.blueRange[1]} </span>
      </div>
    </div>
  </div>
{/if}
