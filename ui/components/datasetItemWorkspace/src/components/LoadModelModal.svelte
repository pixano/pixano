<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { onDestroy } from "svelte";
  import { derived } from "svelte/store";

  import {
    ConfirmModal,
    LoadingModal,
    SelectLocalOrDistantModelModal,
    SelectModal,
    WarningModal,
  } from "@pixano/core";
  import { pixanoInferenceSegmentationModelsStore } from "@pixano/core/src/components/pixano_inference_segmentation/inference";
  import { SAM } from "@pixano/models";

  import {
    datasetSchema,
    isLocalSegmentationModel,
  } from "../../../../apps/pixano/src/lib/stores/datasetStores";
  import { panTool } from "../lib/settings/selectionTools";
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

  const unsubscribeModelsUiStore = modelsUiStore.subscribe((store) => {
    currentModalOpen = store.currentModalOpen;
    selectedModelName =
      store.selectedModelName !== "" ? store.selectedModelName : selectedModelName;
    selectedTableName =
      store.selectedTableName !== "" ? store.selectedTableName : selectedTableName;
  });

  onDestroy(unsubscribeModelsUiStore);

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
    if ($isLocalSegmentationModel) {
      if (selectedModelName && selectedModelName !== "") {
        modelsUiStore.update((store) => ({
          ...store,
          currentModalOpen: "loading",
          selectedModelName,
        }));
        await sam.init("/app_models/" + selectedModelName + ".onnx");
        interactiveSegmenterModel.set(sam);
        modelsUiStore.update((store) => ({ ...store, currentModalOpen: "selectEmbeddingsTable" }));
      } else {
        modelsUiStore.set({
          currentModalOpen: "noModel",
          selectedModelName: "",
          selectedTableName: "",
          yetToLoadEmbedding: true,
        });
        selectedTool.set(panTool);
      }
    } else {
      modelsUiStore.set({
        currentModalOpen: "none",
        selectedModelName: "",
        selectedTableName: "",
        yetToLoadEmbedding: true,
      });
    }
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

  $: if (
    $selectedTool?.isSmart &&
    (($isLocalSegmentationModel && models.length > 0 && !selectedModelName) ||
      (!$isLocalSegmentationModel && $pixanoInferenceSegmentationModelsStore.length === 0))
  ) {
    modelsUiStore.update((store) => ({ ...store, currentModalOpen: "selectModel" }));
  }
</script>

{#if currentModalOpen === "selectModel"}
  <SelectLocalOrDistantModelModal
    choices={models}
    bind:selected={selectedModelName}
    on:confirm={loadModel}
    on:cancel={closeModal}
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
    on:cancel={closeModal}
  />
{/if}
{#if currentModalOpen === "noModel" && $isLocalSegmentationModel}
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
