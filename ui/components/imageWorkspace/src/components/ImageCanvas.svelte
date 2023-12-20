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
  import * as ort from "onnxruntime-web";
  import { Loader2Icon } from "lucide-svelte";
  import { Canvas2D } from "@pixano/canvas2d";
  import type { InteractiveImageSegmenterOutput } from "@pixano/models";
  import type { BBox, DatasetItem, Mask, SelectionTool } from "@pixano/core";

  import { newShape, itemObjects } from "../lib/stores/imageWorkspaceStores";

  export let selectedItem: DatasetItem;
  export let masks: Array<Mask> = [];
  export let bboxes: Array<BBox> = [];
  export let embeddings: Record<string, ort.Tensor>;

  export let selectedTool: SelectionTool;
  export let currentAnn: InteractiveImageSegmenterOutput | null = null;
  export let isLoading: boolean;

  // let loading = true;

  let allIds: string[] = [];

  itemObjects.subscribe((value) => {
    allIds = value.map((item) => item.id);
  });
</script>

<div class="max-w-[100%]">
  {#if isLoading}
    <div class="h-full w-full flex justify-center items-center">
      <Loader2Icon class="animate-spin" />
    </div>
  {:else}
    {#key selectedItem.id}
      <Canvas2D
        {selectedItem}
        colorRange={allIds}
        bind:masks
        bind:bboxes
        {embeddings}
        bind:selectedTool
        bind:currentAnn
        createNewShape={(shape) => newShape.set(shape)}
      />
    {/key}
  {/if}
</div>
