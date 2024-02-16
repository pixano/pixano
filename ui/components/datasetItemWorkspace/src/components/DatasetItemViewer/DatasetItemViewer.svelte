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

  import type { InteractiveImageSegmenterOutput } from "@pixano/models";
  import type { DatasetItem, SelectionTool } from "@pixano/core";

  import ImageViewer from "./ImageViewer.svelte";
  import VideoViewer from "./VideoViewer.svelte";
  import ThreeDimensionsViewer from "./3DViewer.svelte";

  export let selectedItem: DatasetItem;
  export let embeddings: Record<string, ort.Tensor>;

  export let selectedTool: SelectionTool;
  export let currentAnn: InteractiveImageSegmenterOutput | null = null;
  export let isLoading: boolean;

  $: itemType = Object.values(selectedItem.views).map((view) => view.type)[0];
</script>

<div class="max-w-[100%] bg-slate-800">
  {#if isLoading}
    <div class="h-full w-full flex justify-center items-center">
      <Loader2Icon class="animate-spin text-white" />
    </div>
  {:else if itemType === "image"}
    <ImageViewer {selectedItem} {embeddings} bind:selectedTool bind:currentAnn />
  {:else if itemType === "video"}
    <VideoViewer />
  {:else if itemType === "3d"}
    <ThreeDimensionsViewer />
  {/if}
</div>
