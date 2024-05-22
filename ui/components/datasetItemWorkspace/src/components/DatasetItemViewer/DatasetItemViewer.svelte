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
  import type { DatasetItem } from "@pixano/core";

  import {
    newShape,
    itemObjects,
    canSave,
    preAnnotationIsActive,
  } from "../../lib/stores/datasetItemWorkspaceStores";
  import { updateExistingObject } from "../../lib/api/objectsApi";
  import ImageViewer from "./ImageViewer.svelte";
  import VideoViewer from "./VideoViewer.svelte";
  import ThreeDimensionsViewer from "./3DViewer.svelte";

  export let selectedItem: DatasetItem;
  export let embeddings: Record<string, ort.Tensor>;
  export let currentAnn: InteractiveImageSegmenterOutput | null = null;
  export let isLoading: boolean;

  let allIds: string[] = [];

  $: {
    newShape.set($newShape);
    if ($newShape?.status === "editing" && !$preAnnotationIsActive) {
      itemObjects.update((oldObjects) => updateExistingObject(oldObjects, $newShape));
      canSave.update((old) => {
        if (old) return old;
        if ($newShape?.status === "editing" && $newShape.type !== "none") {
          return true;
        }
        return false;
      });
    }
  }

  itemObjects.subscribe((value) => {
    allIds = value.map((item) => item.id);
  });
</script>

<div class="max-w-[100%] bg-slate-800">
  {#if isLoading}
    <div class="h-full w-full flex justify-center items-center">
      <Loader2Icon class="animate-spin text-white" />
    </div>
  {:else if selectedItem.type === "video"}
    <VideoViewer {selectedItem} {embeddings} colorRange={allIds} bind:currentAnn />
  {:else if selectedItem.type === "image" || !selectedItem.type}
    <ImageViewer {selectedItem} {embeddings} bind:currentAnn colorRange={allIds} />
  {:else if selectedItem.type === "3d"}
    <ThreeDimensionsViewer />
  {/if}
</div>
