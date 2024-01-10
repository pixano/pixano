<script lang="ts">
  /**
   * @copyright CEA
   * @author CEA
   * @license CECILL
   *
   * This software is a collaborative computer program whose purpose is to
   * generate and explore labeled data for computer vision applications.
   * This software is governed by the CeCILL-C license under French law and
   * abiding by the rules of distribution of free software. You can use,
   * modify and/ or redistribute the software under the terms of the CeCILL-C
   * license as circulated by CEA, CNRS and INRIA at the following URL
   *
   * http://www.cecill.info
   */

  import { onMount } from "svelte";

  import { SelectModal, WarningModal } from "@pixano/core";
  import { SAM } from "@pixano/models";
  import type { DatasetInfo, DatasetItem, SelectionTool } from "@pixano/core";
  import { loadEmbeddings } from "../lib/api/modelsApi";
  import { interactiveSegmenterModel } from "../lib/stores/imageWorkspaceStores";
  import type { Embeddings } from "../lib/types/imageWorkspaceTypes";

  export let models: Array<string>;
  export let currentDatasetId: DatasetInfo["id"];
  export let selectedItemId: DatasetItem["id"];
  export let embeddings: Embeddings;
  export let selectedTool: SelectionTool;

  let currentModalOpen: "selectModel" | "noModel" | "noEmbeddings" | "none" = "none";
  let selectedModelName: string;

  const sam = new SAM();

  async function loadModel() {
    currentModalOpen = "none";
    await sam.init("/data/models/" + selectedModelName);
    interactiveSegmenterModel.set(sam);
  }

  $: console.log({ embeddings });

  $: {
    // load embeddings when selected item changes
    if (selectedItemId && selectedModelName) {
      loadEmbeddings(selectedItemId, selectedModelName, currentDatasetId)
        .then((results) => {
          embeddings = results;
        })
        .catch((err) => {
          console.error("cannot load Embeddings", err);
        });
    }
  }

  onMount(async () => {
    if (models.length > 0) {
      let samModels = models.filter((m) => m.includes("sam"));
      if (samModels.length == 1) {
        selectedModelName = samModels[0];
        await loadModel();
      }
    }
  });

  $: {
    if (selectedTool?.isSmart && models.length > 1 && !selectedModelName) {
      currentModalOpen = "selectModel";
    }
    if (selectedTool?.isSmart && models.length == 0) {
      currentModalOpen = "noModel";
    }
    if (selectedTool?.isSmart && !!Object.keys(embeddings).length) {
      currentModalOpen = "noEmbeddings";
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
    on:confirm={() => (currentModalOpen = "none")}
  />
{/if}
{#if currentModalOpen === "noEmbeddings"}
  <WarningModal
    message="No embeddings found for model {selectedModelName}."
    details="Please refer to our interactive annotation notebook for information on how to compute embeddings on your dataset."
    on:confirm={() => (currentModalOpen = "none")}
  />
{/if}
