<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { onDestroy } from "svelte";

  import { LoadingModal, SelectLocalOrDistantModelModal } from "@pixano/core";
  import {
    segmentationModels,
    selectedSegmentationModelName,
  } from "@pixano/core/src/lib/stores/inferenceStore";

  import { panTool } from "../lib/settings/selectionTools";
  import { modelsUiStore, selectedTool } from "../lib/stores/datasetItemWorkspaceStores";
  import type { ModelSelection } from "../lib/types/datasetItemWorkspaceTypes";

  let currentModalOpen: ModelSelection["currentModalOpen"] = "none";

  const unsubscribeModelsUiStore = modelsUiStore.subscribe((store) => {
    currentModalOpen = store.currentModalOpen;
  });

  onDestroy(unsubscribeModelsUiStore);

  function loadModel() {
    // Remote-only: just close modal, the selected model name is stored in selectedSegmentationModelName
    modelsUiStore.set({
      currentModalOpen: "none",
      selectedModelName: $selectedSegmentationModelName ?? "",
      selectedTableName: "",
      yetToLoadEmbedding: true,
    });
  }

  const closeModal = () => {
    modelsUiStore.set({
      currentModalOpen: "none",
      selectedModelName: "",
      selectedTableName: "",
      yetToLoadEmbedding: true,
    });
    selectedTool.set(panTool);
  };

  $: if ($selectedTool?.isSmart && $segmentationModels.length === 0) {
    modelsUiStore.update((store) => ({ ...store, currentModalOpen: "selectModel" }));
  }
</script>

{#if currentModalOpen === "selectModel"}
  <SelectLocalOrDistantModelModal on:confirm={loadModel} on:cancel={closeModal} />
{/if}
{#if currentModalOpen === "loading"}
  <LoadingModal />
{/if}
