<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { Plus, Sparkles } from "lucide-svelte";

  import {
    api,
    IconButton,
    MultimodalImageNLPTask,
    QuestionTypeEnum,
    type SystemPrompt,
  } from "@pixano/core";

  import { pixanoInferenceStore } from "../../../../../apps/pixano/src/lib/stores/datasetStores";
  import { connect } from "../../utils/connect";
  import { updatedPixanoInferenceStore } from "../../utils/updatePixInfStore";
  import AddModelModal from "./AddModelModal.svelte";
  import ConnectModal from "./ConnectModal.svelte";

  let selectedModel: string;
  let defaultURL = "http://localhost:9152";
  let isConnected = false;
  let models: { id: string; value: string }[] = [];

  //reactive: if no model selected and there is available model, select first
  $: if (!selectedModel && models.length >= 1) {
    selectedModel = models[0].value;
  }

  //reactive: when model selected, update store
  $: if (selectedModel) {
    pixanoInferenceStore.update((pis) =>
      pis.map((pi) => {
        if (
          pi.task === MultimodalImageNLPTask.CONDITIONAL_GENERATION &&
          pi.name === selectedModel
        ) {
          pi.selected = true;
        }
        return pi;
      }),
    );
  }

  //Try to connect with default URL at startup
  api.isInferenceApiHealthy(defaultURL).then((status) => {
    isConnected = status;
    if (isConnected) listModels();
  });

  const listModels = () => {
    api
      .listModels()
      .then((available_models) => {
        const defaultPrompts: SystemPrompt[] = Object.values(QuestionTypeEnum)
          .filter((value) => typeof value === "string")
          .map(
            (qtype) => ({ content: "", question_type: qtype, as_system: true }), //TODO? give a default system prompt ?
          );
        pixanoInferenceStore.update((currentList) =>
          updatedPixanoInferenceStore(available_models, currentList, defaultPrompts),
        );
        models = available_models
          .filter((model) => model.task === MultimodalImageNLPTask.CONDITIONAL_GENERATION)
          .map((model) => {
            return { id: model.name, value: model.name };
          });
      })
      .catch((err) => {
        console.error("Can't list models", err);
        models = [];
      });
  };

  let showConnectModal = false;
  let showAddModelModal = false;

  const handleOpenConnectModal = (event: MouseEvent) => {
    // stopPropgation is not called as event modifier
    // because event modifiers can only be used on DOM elements
    event.stopPropagation();
    if (showConnectModal) {
      handleCloseConnectModal();
    } else {
      showConnectModal = true;
      document.body.addEventListener("click", handleCloseConnectModal);
    }
  };

  const handleCloseConnectModal = () => {
    showConnectModal = false;
    document.body.removeEventListener("click", handleCloseConnectModal);
  };

  const handleOpenAddModelModal = (event: MouseEvent) => {
    // stopPropgation is not called as event modifier
    // because event modifiers can only be used on DOM elements
    event.stopPropagation();
    if (showAddModelModal) {
      handleCloseAddModelModal();
    } else {
      showAddModelModal = true;
      document.body.addEventListener("click", handleCloseAddModelModal);
    }
  };

  const handleCloseAddModelModal = () => {
    showAddModelModal = false;
    document.body.removeEventListener("click", handleCloseAddModelModal);
  };

  const handleKeyDown = (
    event: KeyboardEvent & {
      currentTarget: EventTarget & Window;
    },
  ) => {
    if (event.key === "Escape") {
      if ((event.target as Element)?.tagName === "INPUT") return event.preventDefault();
      showConnectModal = false;
      showAddModelModal = false;
    }
  };
</script>

<div class="flex flex-row gap-2 justify-between">
  <IconButton tooltipContent="Pixano Inference connection" on:click={handleOpenConnectModal}>
    <Sparkles
      class={`${isConnected ? (selectedModel && selectedModel !== "" ? "text-green-500" : "text-yellow-500") : "text-red-500"}`}
    />
  </IconButton>
  {#if showConnectModal}
    <ConnectModal
      bind:isConnected
      {defaultURL}
      on:listModels={listModels}
      on:cancelConnect={handleCloseConnectModal}
    />
  {/if}
  <div class="flex flex-col grow">
    <!-- For some reason, some tailwind classes don't work on select -->
    <!-- Use style instead -->
    <select
      class="py-3 px-2 border rounded-lg border-gray-200 outline-none text-slate-800"
      style="color: #1e293b; border-color: #e5e7eb;"
      bind:value={selectedModel}
    >
      <option value="" selected disabled>Select a model</option>
      {#each models as { id, value }}
        <option value={id}>{value}</option>
      {/each}
    </select>
  </div>
  <IconButton
    tooltipContent="Instantiate a model"
    disabled={!isConnected}
    on:click={handleOpenAddModelModal}
  >
    <Plus />
  </IconButton>
  {#if showAddModelModal}
    <AddModelModal on:listModels={listModels} on:cancelAddModel={handleCloseAddModelModal} />
  {/if}
</div>
<svelte:window on:keydown={handleKeyDown} />
