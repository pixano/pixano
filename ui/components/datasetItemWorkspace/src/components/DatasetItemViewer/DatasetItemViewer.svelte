<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { Loader2Icon } from "lucide-svelte";
  import * as ort from "onnxruntime-web";

  import type { DatasetItem } from "@pixano/core";
  import type { InteractiveImageSegmenterOutput } from "@pixano/models";

  import ThreeDimensionsViewer from "./3DViewer.svelte";
  import ImageViewer from "./ImageViewer.svelte";
  import TextImageViewer from "./TextImageViewer.svelte";
  import VideoViewer from "./VideoViewer.svelte";

  export let selectedItem: DatasetItem;
  export let embeddings: Record<string, ort.Tensor>;
  export let currentAnn: InteractiveImageSegmenterOutput | null = null;
  export let isLoading: boolean;
  export let headerHeight: number;
</script>

<div class="max-w-[100%] bg-slate-800" style={`max-height: calc(100vh - ${headerHeight}px)`}>
  {#if isLoading}
    <div class="h-full w-full flex justify-center items-center">
      <Loader2Icon class="animate-spin text-white" />
    </div>
  {:else if selectedItem.ui.type === "video"}
    <VideoViewer {selectedItem} {embeddings} bind:currentAnn />
  {:else if selectedItem.ui.type === "vqa"}
    <TextImageViewer {selectedItem} {embeddings} bind:currentAnn />
  {:else if selectedItem.ui.type === "image" || !selectedItem.ui.type}
    <ImageViewer {selectedItem} {embeddings} bind:currentAnn />
  {:else if selectedItem.ui.type === "3d"}
    <ThreeDimensionsViewer />
  {/if}
</div>
