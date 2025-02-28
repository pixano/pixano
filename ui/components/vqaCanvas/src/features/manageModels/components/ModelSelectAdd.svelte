<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { Plus, Sparkles } from "lucide-svelte";
  import { onMount } from "svelte";

  import {
    api,
    IconButton,
    MultimodalImageNLPTask,
    QuestionTypeEnum,
    type SystemPrompt,
  } from "@pixano/core";

  import { pixanoInferenceStore } from "../../../../../apps/pixano/src/lib/stores/datasetStores";
  import { updatedPixanoInferenceStore } from "../../utils/updatePixInfStore";
  import AddModelModal from "./AddModelModal.svelte";
  import ConnectModal from "./ConnectModal.svelte";

  export let vqaSectionWidth: number;
  export let selectedModel: string;

  let defaultURL = "http://localhost:9152";
  let isInferenceApiConnected = false;
  let inferenceModels: { id: string; value: string }[] = [];

  //reactive: when model selected, update store
  $: if (selectedModel) {
    pixanoInferenceStore.update((pis) =>
      pis.map((pi) =>
        pi.task === MultimodalImageNLPTask.CONDITIONAL_GENERATION && pi.name === selectedModel
          ? { ...pi, selected: true }
          : { ...pi, selected: false },
      ),
    );
  }

  //Try to connect with default URL at startup
  onMount(() => {
    api
      .isInferenceApiHealthy(defaultURL)
      .then((status) => {
        isInferenceApiConnected = status;
        if (isInferenceApiConnected) listModels();
      })
      .catch(() => console.error("Cannot connect to inference API"));
  });

  const listModels = () => {
    api
      .listModels()
      .then((available_models) => {
        const defaultPrompts: SystemPrompt[] = Object.values(QuestionTypeEnum).map(
          (qtype) => ({ content: "", question_type: qtype, as_system: true }), //TODO? give a default system prompt ?
        );

        pixanoInferenceStore.update((currentList) =>
          updatedPixanoInferenceStore(available_models, currentList, defaultPrompts),
        );

        inferenceModels = available_models
          .filter((model) => model.task === MultimodalImageNLPTask.CONDITIONAL_GENERATION)
          .map((model) => ({ id: model.name, value: model.name }));

        if (inferenceModels.length > 0) {
          selectedModel = inferenceModels[0].value;
        }
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

<div class="px-3 flex flex-row gap-2">
  <div class="flex-none content-center">
    <IconButton tooltipContent="Pixano Inference connection" on:click={handleOpenConnectModal}>
      <Sparkles
        size={20}
        class={isInferenceApiConnected
          ? selectedModel
            ? "text-green-500"
            : "text-yellow-500"
          : "text-red-500"}
      />
    </IconButton>
    {#if showConnectModal}
      <ConnectModal
        bind:isConnected={isInferenceApiConnected}
        {defaultURL}
        on:cancelConnect={handleCloseConnectModal}
        on:listModels={listModels}
      />
    {/if}
  </div>
  <div class="flex flex-col grow">
    <!-- For some reason, some tailwind classes don't work on select -->
    <!-- Use style instead -->
    <select
      class="py-3 px-2 border rounded-lg border-gray-200 outline-none text-slate-800"
      style="color: #1e293b; border-color: #e5e7eb;"
      bind:value={selectedModel}
    >
      <option value="" selected disabled>Select a model</option>
      {#each inferenceModels as { id, value }}
        <option value={id}>{value}</option>
      {/each}
    </select>
  </div>

  <div class="flex-none content-center">
    <IconButton
      tooltipContent="Instantiate a model"
      disabled={!isInferenceApiConnected}
      on:click={handleOpenAddModelModal}
    >
      <Plus />
    </IconButton>
    {#if showAddModelModal}
      <AddModelModal
        {vqaSectionWidth}
        on:listModels={listModels}
        on:cancelAddModel={handleCloseAddModelModal}
      />
    {/if}
  </div>
</div>
<svelte:window on:keydown={handleKeyDown} />
