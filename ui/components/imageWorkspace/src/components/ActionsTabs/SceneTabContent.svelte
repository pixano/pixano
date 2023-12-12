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

  import { itemMetas } from "../../lib/stores/stores";
  import type { ItemFeature } from "@pixano/core";

  type ImageMeta = {
    width: number;
    height: number;
    format: string;
    id: string;
  };

  let features: ItemFeature[];
  let imageMeta: ImageMeta[] = [];

  itemMetas.subscribe((metas) => {
    imageMeta = Object.values(metas.views).map((view) => ({
      width: view.features.width.value as number,
      height: view.features.height.value as number,
      format: view.uri.split(".").at(-1) as string,
      id: view.id,
    }));
    features = Object.values(metas.features).map((feature) => ({
      ...feature,
      name: feature.name.replace(/_/g, " "),
    }));
  });
</script>

<div class="border-b-2 border-b-gray-500 p-4 mb-4">
  <h3 class="uppercase font-extralight">Features</h3>
  <div class="mt-4 pb-8">
    {#each features as feature}
      <p class="mb-1 mt-3">{feature.name}</p>
      <div class="flex gap-1 flex-wrap">
        <div
          class="flex items-center rounded-2xl bg-primary-light py-1 px-4 first-letter:uppercase w-fit"
        >
          <p class="font-extralight first-letter:uppercase">{feature.value}</p>
        </div>
      </div>
    {/each}
  </div>
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
