<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { untrack } from "svelte";

  import SelectLocalOrDistantModelModal from "../inference/segmentation/SelectLocalOrDistantModelModal.svelte";
  import {
    segmentationModels,
    selectedSegmentationModel,
  } from "$lib/stores/inferenceStores.svelte";
  import { modelsUiStore, selectedTool } from "$lib/stores/workspaceStores.svelte";
  import { ToolType, panTool } from "$lib/tools";
  import { LoadingModal } from "$lib/ui";

  const currentModalOpen = $derived(modelsUiStore.value.currentModalOpen);

  function loadModel() {
    // Remote-only: keep the selected model name in modelsUiStore for embedding-related flows.
    modelsUiStore.value = {
      currentModalOpen: "none",
      selectedModelName: selectedSegmentationModel.value?.name ?? "",
      selectedTableName: "",
      yetToLoadEmbedding: true,
    };
  }

  const closeModal = () => {
    modelsUiStore.value = {
      currentModalOpen: "none",
      selectedModelName: "",
      selectedTableName: "",
      yetToLoadEmbedding: true,
    };
    selectedTool.value = panTool;
  };

  $effect(() => {
    const tool = selectedTool.value;
    const models = segmentationModels.value;
    const selectedModel = selectedSegmentationModel.value;
    if (
      tool?.type === ToolType.InteractiveSegmenter &&
      (!selectedModel || models.length === 0)
    ) {
      untrack(() => {
        modelsUiStore.update((store) => {
          if (store.currentModalOpen === "selectModel") return store;
          return { ...store, currentModalOpen: "selectModel" };
        });
      });
    }
  });
</script>

{#if currentModalOpen === "selectModel"}
  <SelectLocalOrDistantModelModal onConfirm={loadModel} onCancel={closeModal} />
{/if}
{#if currentModalOpen === "loading"}
  <LoadingModal />
{/if}
