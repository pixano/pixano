<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { onMount } from "svelte";

  import { SelectModal, WarningModal } from "@pixano/core";
  import { SAM } from "@pixano/models";
  import type { DatasetInfo, DatasetItem } from "@pixano/core";
  import { loadEmbeddings as loadEmbeddingsApi } from "../lib/api/modelsApi";
  import {
    interactiveSegmenterModel,
    modelsStore,
    selectedTool,
  } from "../lib/stores/datasetItemWorkspaceStores";
  import type { Embeddings, ModelSelection } from "../lib/types/datasetItemWorkspaceTypes";
  import ConfirmModal from "@pixano/core/src/components/modals/ConfirmModal.svelte";

  export let models: Array<string>;
  export let currentDatasetId: DatasetInfo["id"];
  export let selectedItemId: DatasetItem["id"];
  export let embeddings: Embeddings;

  let currentModalOpen: ModelSelection["currentModalOpen"] = "none";
  let selectedModelName: ModelSelection["selectedModelName"];

  modelsStore.subscribe((store) => {
    currentModalOpen = store.currentModalOpen;
    selectedModelName = store.selectedModelName;
  });

  const loadEmbeddings = () => {
    if (
      !selectedItemId ||
      !selectedModelName ||
      !currentDatasetId ||
      selectedModelName === "none"
    ) {
      return;
    }
    loadEmbeddingsApi(selectedItemId, selectedModelName, currentDatasetId)
      .then((results) => {
        embeddings = results;
      })
      .catch((err) => {
        modelsStore.update((store) => ({ ...store, currentModalOpen: "noEmbeddings" }));
        console.error("cannot load Embeddings", err);
      });
  };

  const sam = new SAM();

  async function loadModel() {
    modelsStore.update((store) => ({ ...store, currentModalOpen: "none" }));
    await sam.init("/data/models/" + selectedModelName);
    interactiveSegmenterModel.set(sam);
    loadEmbeddings();
  }

  $: {
    if (selectedItemId) {
      loadEmbeddings();
    }
  }

  onMount(async () => {
    if (models.length > 0) {
      let samModels = models.filter((m) => m.includes("sam"));
      if (samModels.length == 1) {
        modelsStore.update((store) => ({ ...store, selectedModelName: samModels[0] }));
        await loadModel();
      }
    }
  });

  $: {
    if ($selectedTool?.isSmart && models.length > 1 && !selectedModelName) {
      modelsStore.update((store) => ({ ...store, currentModalOpen: "selectModel" }));
    }
    if ($selectedTool?.isSmart && models.length == 0) {
      modelsStore.update((store) => ({ ...store, currentModalOpen: "noModel" }));
    }
  }

  $: {
    if (selectedModelName) {
      modelsStore.update((store) => ({
        ...store,
        selectedModelName,
      }));
    }
  }
</script>

{#if currentModalOpen === "selectModel"}
  <SelectModal
    message="Please select your model for interactive segmentation."
    choices={models}
    ifNoChoices={""}
    bind:selected={selectedModelName}
    on:confirm={loadModel}
  />
{/if}
{#if currentModalOpen === "noModel"}
  <WarningModal
    message="It looks like there is no model for interactive segmentation in your dataset library."
    details="Please refer to our interactive annotation notebook for information on how to export your model to ONNX."
    on:confirm={() => modelsStore.update((store) => ({ ...store, currentModalOpen: "none" }))}
  />
{/if}
{#if currentModalOpen === "noEmbeddings"}
  <ConfirmModal
    message="No embeddings found for model {selectedModelName}."
    details="Please refer to our interactive annotation notebook for information on how to compute embeddings on your dataset."
    on:confirm={() =>
      modelsStore.update((store) => ({ ...store, currentModalOpen: "selectModel" }))}
    on:cancel={() =>
      modelsStore.update((store) => ({
        ...store,
        currentModalOpen: "none",
        selectedModelName: "none",
      }))}
  />
{/if}
