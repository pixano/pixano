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
  import FeatureInputs from "../Features/FeatureInputs.svelte";

  import { createFeature } from "../../lib/api/featuresApi";
  import type { Feature } from "../../lib/types/imageWorkspaceTypes";

  type ImageMeta = {
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
      width: view.features.width.value as number,
      height: view.features.height.value as number,
      format: view.uri.split(".").at(-1) as string,
      id: view.id,
    }));
    features = createFeature(metas.features);
  });

  const handleEditIconClick = () => {
    isEditing = !isEditing;
  };

  const handleTextInputChange = (value: string | boolean, propertyName: string) => {
    itemMetas.update((oldMetas) => {
      const newMetas = { ...oldMetas };
      newMetas.features = {
        ...newMetas.features,
        [propertyName]: {
          ...newMetas.features[propertyName],
          value,
        },
      };
      return newMetas;
    });
    canSave.set(true);
  };
</script>

<div class="border-b-2 border-b-gray-500 p-4 mb-4">
  <h3 class="uppercase font-extralight">
    <span class="mr-4">Features</span>
    <IconButton selected={isEditing} on:click={handleEditIconClick}
      ><Pencil class="h-4" /></IconButton
    >
  </h3>
  <FeatureInputs {features} {isEditing} saveInputChange={handleTextInputChange} />
</div>
{#each imageMeta as meta}
  <div class="p-4">
    <h3 class="uppercase font-extralight">File {meta.id}</h3>
    <div class="font-extralight mt-4 pb-4">
      <div class="grid gap-4 grid-cols-[100px_auto] mt-2">
        <p class="font-light first-letter:uppercase">Width</p>
        <p>{meta.width}</p>
      </div>
      <div class="grid gap-4 grid-cols-[100px_auto] mt-2">
        <p class="font-light first-letter:uppercase">Height</p>
        <p>{meta.height}</p>
      </div>
      <div class="grid gap-4 grid-cols-[100px_auto] mt-2">
        <p class="font-light first-letter:uppercase">Format</p>
        <p>{meta.format}</p>
      </div>
    </div>
  </div>
{/each}
