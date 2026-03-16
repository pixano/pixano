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
    selectedSegmentationModelName,
  } from "$lib/stores/inferenceStores.svelte";
  import { modelsUiStore, selectedTool } from "$lib/stores/workspaceStores.svelte";
  import { panTool } from "$lib/tools";
  import { LoadingModal } from "$lib/ui";

  const currentModalOpen = $derived(modelsUiStore.value.currentModalOpen);

  function loadModel() {
    // Remote-only: just close modal, the selected model name is stored in selectedSegmentationModelName
    modelsUiStore.value = {
      currentModalOpen: "none",
      selectedModelName: selectedSegmentationModelName.value ?? "",
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
    if (tool?.isSmart && models.length === 0) {
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
