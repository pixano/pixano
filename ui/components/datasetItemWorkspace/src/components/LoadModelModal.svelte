<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { derived } from "svelte/store";

  import { LoadingModal, SelectModal, WarningModal } from "@pixano/core";
  import ConfirmModal from "@pixano/core/src/components/modals/ConfirmModal.svelte";
  import { SAM } from "@pixano/models";

  import { datasetSchema } from "../../../../apps/pixano/src/lib/stores/datasetStores";
  import {
    interactiveSegmenterModel,
    modelsUiStore,
    selectedTool,
  } from "../lib/stores/datasetItemWorkspaceStores";
  import type { ModelSelection } from "../lib/types/datasetItemWorkspaceTypes";

  export let models: Array<string>;

  let currentModalOpen: ModelSelection["currentModalOpen"] = "none";
  let selectedModelName: ModelSelection["selectedModelName"] = models ? models[0] : "";
  let selectedTableName: ModelSelection["selectedTableName"];
  let sortedTablesChoices = derived(datasetSchema, ($datasetSchema) => {
    const withSam = $datasetSchema?.groups.embeddings.filter((t) => t.includes("sam")) ?? [];
    const withoutSam = $datasetSchema?.groups.embeddings.filter((t) => !t.includes("sam")) ?? [];
    return [...withSam, ...withoutSam];
  });

  modelsUiStore.subscribe((store) => {
    currentModalOpen = store.currentModalOpen;
    selectedModelName =
      store.selectedModelName !== "" ? store.selectedModelName : selectedModelName;
    selectedTableName =
      store.selectedTableName !== "" ? store.selectedTableName : selectedTableName;
  });

  const getViewEmbeddings = () => {
    modelsUiStore.update((store) => ({
      ...store,
      selectedTableName,
      yetToLoadEmbedding: true,
      currentModalOpen: "loading",
    }));
  };

  const sam = new SAM();

  async function loadModel() {
    modelsUiStore.update((store) => ({
      ...store,
      currentModalOpen: "loading",
      selectedModelName,
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
    on:confirm={getViewEmbeddings}
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
