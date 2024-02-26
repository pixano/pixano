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

  import type { DatasetItem, SelectionTool } from "@pixano/core";
  import type { InteractiveImageSegmenterOutput } from "@pixano/models";
  import { Canvas2D } from "@pixano/canvas2d";
  import { newShape, itemBboxes, itemMasks } from "../../lib/stores/datasetItemWorkspaceStores";
  import VideoPlayer from "../VideoPlayer/VideoPlayer.svelte";

  export let selectedItem: DatasetItem;
  export let embeddings: Record<string, ort.Tensor>;
  export let selectedTool: SelectionTool;
  export let currentAnn: InteractiveImageSegmenterOutput | null = null;

  let views = selectedItem.views;
  let isLoaded = false; // TODO : refactor when images come from the server

  const updateViews = (imageUrl: string) => {
    views = {
      ...selectedItem.views,
      image: {
        ...selectedItem.views.image,
        uri: imageUrl || selectedItem.views.image.uri,
      },
    };
    isLoaded = true;
  };
</script>

<div class="pl-4 w-full flex flex-col h-full">
  {#if isLoaded}
    <Canvas2D
      selectedItemId={selectedItem.id}
      {views}
      colorRange={[]}
      bboxes={$itemBboxes}
      masks={$itemMasks}
      {embeddings}
      bind:selectedTool
      bind:currentAnn
      bind:newShape={$newShape}
    />
  {/if}
  <VideoPlayer {updateViews} />
</div>
