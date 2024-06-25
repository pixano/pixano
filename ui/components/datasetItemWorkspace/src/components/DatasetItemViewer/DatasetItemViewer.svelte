<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import * as ort from "onnxruntime-web";
  import { Loader2Icon } from "lucide-svelte";

  import type { InteractiveImageSegmenterOutput } from "@pixano/models";
  import type { DatasetItem } from "@pixano/core";

  import {
    newShape,
    canSave,
    preAnnotationIsActive,
  } from "../../lib/stores/datasetItemWorkspaceStores";
  import ImageViewer from "./ImageViewer.svelte";
  import VideoViewer from "./VideoViewer.svelte";
  import ThreeDimensionsViewer from "./3DViewer.svelte";

  export let selectedItem: DatasetItem;
  export let embeddings: Record<string, ort.Tensor>;
  export let currentAnn: InteractiveImageSegmenterOutput | null = null;
  export let isLoading: boolean;
  export let headerHeight: number;

  $: {
    if ($newShape?.status === "editing" && !$preAnnotationIsActive) {
      canSave.update((old) => {
        if (old) return old;
        if ($newShape?.status === "editing" && $newShape.type !== "none") {
          return true;
        }
        return false;
      });
    }
  }
</script>

<div class="max-w-[100%] bg-slate-800" style={`max-height: calc(100vh - ${headerHeight}px)`}>
  {#if isLoading}
    <div class="h-full w-full flex justify-center items-center">
      <Loader2Icon class="animate-spin text-white" />
    </div>
  {:else if selectedItem.type === "video"}
    <VideoViewer {selectedItem} {embeddings} bind:currentAnn />
  {:else if selectedItem.type === "image" || !selectedItem.type}
    <ImageViewer {selectedItem} {embeddings} bind:currentAnn />
  {:else if selectedItem.type === "3d"}
    <ThreeDimensionsViewer />
  {/if}
</div>
