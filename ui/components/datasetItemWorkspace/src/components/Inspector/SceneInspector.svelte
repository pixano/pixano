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

  import { IconButton, type ItemView } from "@pixano/core/src";

  import { canSave, itemMetas } from "../../lib/stores/datasetItemWorkspaceStores";
  import UpdateFeatureInputs from "../Features/UpdateFeatureInputs.svelte";

  import { createFeature } from "../../lib/api/featuresApi";
  import type { Feature } from "../../lib/types/datasetItemWorkspaceTypes";
  import { defaultSceneFeatures } from "../../lib/settings/defaultFeatures";
  import type { Filters } from "@pixano/canvas2d/src/lib/types/canvas2dTypes";

  export let filters: Filters;
  export let RGB = {
    r: 0,
    g: 0,
    b: 0,
  };

  type ImageMeta = {
    fileName: string;
    width: number;
    height: number;
    format: string;
    id: string;
  };

  let features: Feature[];
  let imageMeta: ImageMeta[] = [];
  let isEditing: boolean = false;

  itemMetas.subscribe((metas) => {
    imageMeta = Object.values(metas.views).map((view: ItemView | ItemView[]) => {
      const image: ItemView = Array.isArray(view) ? view[0] : view;
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
  {#each imageMeta as meta}
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

<!-- FILTERS -->
<div class="p-4 pb-8 border-b-2 border-b-slate-500 text-slate-800 font-medium">
  <h3 class="uppercase font-medium h-10">FILTERS</h3>
  <div class="mx-4 mb-4">
    <label for="brightness">Brightness : {Math.round(filters.brightness * 100 + 50)}%</label>
    <input
      type="range"
      id="brightness"
      min="-0.5"
      max="0.5"
      step="0.01"
      class="w-full mt-1 cursor-pointer accent-primary"
      bind:value={filters.brightness}
    />

    <label for="contrast">Contrast : {Math.round(filters.contrast + 50)}%</label>
    <input
      type="range"
      id="contrast"
      min="-50"
      max="50"
      step="1"
      class="w-full mt-1 cursor-pointer accent-primary"
      bind:value={filters.contrast}
    />

    <!-- WIP -->
    <div class="pt-2 flex items-center space-x-2">
      <input
        type="checkbox"
        id="equalizer"
        class="cursor-pointer w-4 h-4"
        bind:checked={filters.equalizeHistogram}
      />
      <label for="equalizer" class="select-none cursor-pointer"> Equalize histogram </label>
    </div>

    <div class="pt-4">Color thresholds</div>
    <div class="flex items-center space-x-2">
      <label for="red" class="text-red-500"> R </label>
      <input
        type="range"
        id="red"
        min="0"
        max="255"
        step="1"
        class="w-full mt-1 cursor-pointer accent-red-500"
        bind:value={RGB.r}
      />
      <span class="w-8 text-sm text-center text-red-500">{RGB.r}</span>
    </div>
    <div class="flex items-center space-x-2">
      <label for="green" class="text-green-500"> G </label>
      <input
        type="range"
        id="green"
        min="0"
        max="255"
        step="1"
        class="w-full mt-1 cursor-pointer accent-green-500"
        bind:value={RGB.g}
      />
      <span class="w-8 text-sm text-center text-green-500">{RGB.g}</span>
    </div>
    <div class="flex items-center space-x-2">
      <label for="blue" class="text-blue-500"> B </label>
      <input
        type="range"
        id="blue"
        min="0"
        max="255"
        step="1"
        class="w-full mt-1 cursor-pointer accent-blue-500"
        bind:value={RGB.b}
      />
      <span class="w-8 text-sm text-center text-blue-500">{RGB.b}</span>
    </div>
  </div>
</div>
