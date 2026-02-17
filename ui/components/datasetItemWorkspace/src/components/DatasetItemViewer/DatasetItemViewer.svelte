<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { Loader2Icon } from "lucide-svelte";
  import { onDestroy } from "svelte";

  import { WorkspaceType, type DatasetItem } from "@pixano/core";

  import { loadViewEmbeddings } from "../../lib/api/modelsApi";
  import { modelsUiStore } from "../../lib/stores/datasetItemWorkspaceStores";
  import ThreeDimensionsViewer from "./3DViewer.svelte";
  import EntityLinkingViewer from "./EntityLinkingViewer.svelte";
  import ImageViewer from "./ImageViewer.svelte";
  import VideoViewer from "./VideoViewer.svelte";
  import VqaViewer from "./VqaViewer.svelte";

  export let selectedItem: DatasetItem;
  export let isLoading: boolean;
  export let resize: number;

  const unsubscribeModelsUiStore = modelsUiStore.subscribe(() => {
    if (selectedItem) loadViewEmbeddings();
  });

  onDestroy(unsubscribeModelsUiStore);
</script>

<div class="h-full w-full max-w-full bg-canvas overflow-hidden">
  {#if isLoading}
    <div class="h-full w-full flex justify-center items-center">
      <Loader2Icon class="animate-spin text-white" />
    </div>
  {:else if selectedItem.ui.type === WorkspaceType.VIDEO}
    <VideoViewer {selectedItem} {resize} />
  {:else if selectedItem.ui.type === WorkspaceType.IMAGE_VQA}
    <VqaViewer {selectedItem} {resize} />
  {:else if selectedItem.ui.type === WorkspaceType.IMAGE_TEXT_ENTITY_LINKING}
    <EntityLinkingViewer {selectedItem} {resize} />
  {:else if selectedItem.ui.type === WorkspaceType.IMAGE || !selectedItem.ui.type}
    <ImageViewer {selectedItem} {resize} />
  {:else if selectedItem.ui.type === WorkspaceType.PCL_3D}
    <ThreeDimensionsViewer />
  {/if}
</div>
