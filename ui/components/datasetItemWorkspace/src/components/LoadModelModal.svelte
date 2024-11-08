<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { SelectModal, WarningModal, DatasetInfo } from "@pixano/core";
  import { SAM } from "@pixano/models";
  import { loadViewEmbeddings as loadViewEmbeddingsAPI } from "../lib/api/modelsApi";
  import {
    interactiveSegmenterModel,
    modelsStore,
    selectedTool,
  } from "../lib/stores/datasetItemWorkspaceStores";
  import { datasetSchema } from "../../../../apps/pixano/src/lib/stores/datasetStores";
  import type { Embeddings, ModelSelection } from "../lib/types/datasetItemWorkspaceTypes";
  import ConfirmModal from "@pixano/core/src/components/modals/ConfirmModal.svelte";

  export let models: Array<string>;
  export let currentDatasetId: DatasetInfo["id"];
  export let selectedItemId: string;
  export let embeddings: Embeddings;

  let currentModalOpen: ModelSelection["currentModalOpen"] = "none";
  let selectedModelName: ModelSelection["selectedModelName"];
  let selectedTableName: string;

  modelsStore.subscribe((store) => {
    currentModalOpen = store.currentModalOpen;
    selectedModelName = store.selectedModelName;
  });

  const loadViewEmbeddings = () => {
    modelsStore.update((store) => ({ ...store, currentModalOpen: "none" }));
    if (
      !selectedItemId ||
      !selectedTableName ||
      !currentDatasetId ||
      selectedModelName === "none"
    ) {
      return;
    }
    loadViewEmbeddingsAPI(selectedItemId, selectedTableName, currentDatasetId)
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
    modelsStore.update((store) => ({
      ...store,
      currentModalOpen: "none",
      selectedModelName: selectedModelName,
    }));
    await sam.init("/app_models/" + selectedModelName + ".onnx");
    interactiveSegmenterModel.set(sam);
    modelsStore.update((store) => ({ ...store, currentModalOpen: "selectEmbeddingsTable" }));
  }

  $: {
    if ($selectedTool?.isSmart && models.length > 1 && !selectedModelName) {
      modelsStore.update((store) => ({ ...store, currentModalOpen: "selectModel" }));
    }
    if ($selectedTool?.isSmart && models.length == 0) {
      modelsStore.update((store) => ({ ...store, currentModalOpen: "noModel" }));
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
{#if currentModalOpen === "selectEmbeddingsTable"}
  <SelectModal
    message="Please select the embeddings table for the model."
    choices={$datasetSchema.groups.embeddings}
    ifNoChoices={""}
    bind:selected={selectedTableName}
    on:confirm={loadViewEmbeddings}
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
