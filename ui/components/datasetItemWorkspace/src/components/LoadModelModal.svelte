<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { derived } from "svelte/store";
  import { SelectModal, WarningModal, LoadingModal, DatasetInfo } from "@pixano/core";
  import { SAM } from "@pixano/models";
  import { loadViewEmbeddings as loadViewEmbeddingsAPI } from "../lib/api/modelsApi";
  import {
    interactiveSegmenterModel,
    modelsUiStore,
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
  let selectedModelName: ModelSelection["selectedModelName"] = models ? models[0] : "";
  let selectedTableName: string;
  let sortedTablesChoices = derived(datasetSchema, ($datasetSchema) => {
    const withSam = $datasetSchema.groups.embeddings.filter((t) => t.includes("sam"));
    const withoutSam = $datasetSchema.groups.embeddings.filter((t) => !t.includes("sam"));
    return [...withSam, ...withoutSam];
  });

  modelsUiStore.subscribe((store) => {
    currentModalOpen = store.currentModalOpen;
    selectedModelName =
      store.selectedModelName !== "" ? store.selectedModelName : selectedModelName;
  });

  const loadViewEmbeddings = () => {
    modelsUiStore.update((store) => ({ ...store, currentModalOpen: "none" }));
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
        modelsUiStore.update((store) => ({ ...store, currentModalOpen: "noEmbeddings" }));
        console.error("cannot load Embeddings", err);
      });
  };

  const sam = new SAM();

  async function loadModel() {
    modelsUiStore.update((store) => ({
      ...store,
      currentModalOpen: "loading",
      selectedModelName: selectedModelName,
    }));
    await sam.init("/app_models/" + selectedModelName + ".onnx");
    interactiveSegmenterModel.set(sam);
    modelsUiStore.update((store) => ({ ...store, currentModalOpen: "selectEmbeddingsTable" }));
  }

  $: {
    if ($selectedTool?.isSmart && models.length > 1 && !selectedModelName) {
      modelsUiStore.update((store) => ({ ...store, currentModalOpen: "selectModel" }));
    }
    if ($selectedTool?.isSmart && models.length == 0) {
      modelsUiStore.update((store) => ({ ...store, currentModalOpen: "noModel" }));
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
{#if currentModalOpen === "loading"}
  <LoadingModal />
{/if}
{#if currentModalOpen === "selectEmbeddingsTable"}
  <SelectModal
    message="Please select the embeddings table for the model."
    choices={$sortedTablesChoices}
    ifNoChoices={""}
    bind:selected={selectedTableName}
    on:confirm={loadViewEmbeddings}
  />
{/if}
{#if currentModalOpen === "noModel"}
  <WarningModal
    message="It looks like there is no model for interactive segmentation in your dataset library."
    details="Please refer to our interactive annotation notebook for information on how to export your model to ONNX."
    on:confirm={() => modelsUiStore.update((store) => ({ ...store, currentModalOpen: "none" }))}
  />
{/if}
{#if currentModalOpen === "noEmbeddings"}
  <ConfirmModal
    message="No embeddings found for model {selectedModelName}."
    details="Please refer to our interactive annotation notebook for information on how to compute embeddings on your dataset."
    on:confirm={() =>
      modelsUiStore.update((store) => ({ ...store, currentModalOpen: "selectModel" }))}
    on:cancel={() =>
      modelsUiStore.update((store) => ({
        ...store,
        currentModalOpen: "none",
        selectedModelName: "none",
      }))}
  />
{/if}
