<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { Loader2Icon } from "lucide-svelte";

  import { WorkspaceType, type DatasetItem } from "@pixano/core";
  import type { InteractiveImageSegmenterOutput } from "@pixano/models";

  import ThreeDimensionsViewer from "./3DViewer.svelte";
  import EntityLinkingViewer from "./EntityLinkingViewer.svelte";
  import ImageViewer from "./ImageViewer.svelte";
  import VideoViewer from "./VideoViewer.svelte";
  import VqaViewer from "./VqaViewer.svelte";

  export let selectedItem: DatasetItem;
  export let currentAnn: InteractiveImageSegmenterOutput | null = null;
  export let isLoading: boolean;
</script>

<div class="max-h-[calc(100vh-80px)] max-w-full bg-slate-800">
  {#if isLoading}
    <div class="h-full w-full flex justify-center items-center">
      <Loader2Icon class="animate-spin text-white" />
    </div>
  {:else if selectedItem.ui.type === WorkspaceType.VIDEO}
    <VideoViewer {selectedItem} bind:currentAnn />
  {:else if selectedItem.ui.type === WorkspaceType.IMAGE_VQA}
    <VqaViewer {selectedItem} bind:currentAnn />
  {:else if selectedItem.ui.type === WorkspaceType.IMAGE_TEXT_ENTITY_LINKING}
    <EntityLinkingViewer {selectedItem} bind:currentAnn />
  {:else if selectedItem.ui.type === WorkspaceType.IMAGE || !selectedItem.ui.type}
    <ImageViewer {selectedItem} bind:currentAnn />
  {:else if selectedItem.ui.type === WorkspaceType.PCL_3D}
    <ThreeDimensionsViewer />
  {/if}
</div>
