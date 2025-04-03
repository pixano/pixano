<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { Loader2Icon } from "lucide-svelte";
  import * as ort from "onnxruntime-web";
  import { afterUpdate } from "svelte";

  import { WorkspaceType, type DatasetItem } from "@pixano/core";
  import type { InteractiveImageSegmenterOutput } from "@pixano/models";

  import { loadViewEmbeddings } from "../../lib/api/modelsApi";
  import { modelsUiStore } from "../../lib/stores/datasetItemWorkspaceStores";
  import ThreeDimensionsViewer from "./3DViewer.svelte";
  import EntityLinkingViewer from "./EntityLinkingViewer.svelte";
  import ImageViewer from "./ImageViewer.svelte";
  import VideoViewer from "./VideoViewer.svelte";
  import VqaViewer from "./VqaViewer.svelte";

  export let selectedItem: DatasetItem;
  export let currentAnn: InteractiveImageSegmenterOutput | null = null;
  export let isLoading: boolean;
  export let resize: number;

  let embeddings: Record<string, ort.Tensor> = {};

  afterUpdate(() => {
    if (
      selectedItem &&
      $modelsUiStore.yetToLoadEmbedding &&
      $modelsUiStore.selectedModelName !== "" &&
      $modelsUiStore.selectedTableName !== ""
    ) {
      modelsUiStore.update((store) => ({ ...store, yetToLoadEmbedding: false }));
      loadViewEmbeddings(
        selectedItem.item.id,
        $modelsUiStore.selectedTableName,
        selectedItem.ui.datasetId,
      )
        .then((results) => {
          embeddings = results;
          modelsUiStore.update((store) => ({
            ...store,
            currentModalOpen: "none",
          }));
        })
        .catch((err) => {
          modelsUiStore.update((store) => ({
            ...store,
            selectedTableName: "",
            currentModalOpen: "noEmbeddings",
          }));
          console.error("cannot load Embeddings", err);
          embeddings = {};
        });
    }
  });
</script>

<div class="max-h-[calc(100vh-80px)] w-full max-w-full bg-slate-800">
  {#if isLoading}
    <div class="h-full w-full flex justify-center items-center">
      <Loader2Icon class="animate-spin text-white" />
    </div>
  {:else if selectedItem.ui.type === WorkspaceType.VIDEO}
    <VideoViewer {selectedItem} {embeddings} {resize} bind:currentAnn />
  {:else if selectedItem.ui.type === WorkspaceType.IMAGE_VQA}
    <VqaViewer {selectedItem} {embeddings} {resize} bind:currentAnn />
  {:else if selectedItem.ui.type === WorkspaceType.IMAGE_TEXT_ENTITY_LINKING}
    <EntityLinkingViewer {selectedItem} {embeddings} {resize} bind:currentAnn />
  {:else if selectedItem.ui.type === WorkspaceType.IMAGE || !selectedItem.ui.type}
    <ImageViewer {selectedItem} {embeddings} {resize} bind:currentAnn />
  {:else if selectedItem.ui.type === WorkspaceType.PCL_3D}
    <ThreeDimensionsViewer />
  {/if}
</div>
