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

  import { IconButton } from "@pixano/core/src";

  import { canSave, itemMetas } from "../../lib/stores/imageWorkspaceStores";
  import UpdateFeatureInputs from "../Features/UpdateFeatureInputs.svelte";

  import { createFeature } from "../../lib/api/featuresApi";
  import type { Feature } from "../../lib/types/imageWorkspaceTypes";
  import { defaultSceneFeatures } from "../../lib/settings/defaultFeatures";

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
    imageMeta = Object.values(metas.views || {}).map((view) => ({
      fileName: view.uri.split("/").at(-1) as string,
      width: view.features.width.value as number,
      height: view.features.height.value as number,
      format: view.uri.split(".").at(-1)?.toUpperCase() as string,
      id: view.id,
    }));
    const sceneFeatures = Object.values(metas.sceneFeatures).length
      ? metas.sceneFeatures
      : defaultSceneFeatures;
    features = createFeature(sceneFeatures);
  });

  const handleEditIconClick = () => {
    isEditing = !isEditing;
  };

  const handleTextInputChange = (value: string | boolean | number, propertyName: string) => {
    itemMetas.update((oldMetas) => {
      const newMetas = { ...oldMetas };
      newMetas.sceneFeatures = {
        ...newMetas.sceneFeatures,
        [propertyName]: {
          ...(newMetas.sceneFeatures?.[propertyName] || defaultSceneFeatures[propertyName]),
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
      featureClass="scene"
      {features}
      {isEditing}
      saveInputChange={handleTextInputChange}
    />
  </div>
</div>
<div class="p-4 text-slate-800">
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
