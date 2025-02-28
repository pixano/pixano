<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { Plus, Sparkles } from "lucide-svelte";
  import { onMount } from "svelte";
  import { api, IconButton, MultimodalImageNLPTask, QuestionTypeEnum } from "@pixano/core";

  import {
    completionModelsStore,
    type QuestionGenerationSystemPrompts,
  } from "../../../stores/completionModels";
  import { mergeModelLists } from "../../../utils/mergeModelsList";
  import AddModelModal from "./AddModelModal.svelte";
  import ConnectModal from "./ConnectModal.svelte";

  export let vqaSectionWidth: number;

  let selectedModel: string;

  let defaultURL = "http://localhost:9152";
  let isInferenceApiConnected = false;
  let inferenceModels: { id: string; value: string }[] = [];

  //reactive: when model selected, update store
  $: completionModelsStore.update((models) =>
    models.map((model) =>
      model.name === selectedModel ? { ...model, selected: true } : { ...model, selected: false },
    ),
  );

  //reactive: when no model selected and model available, select first one
  $: if (!selectedModel && inferenceModels.length >= 1) {
    selectedModel = inferenceModels[0].id;
  }

  async function connectToPixanoInference() {
    isInferenceApiConnected = await api.isInferenceApiHealthy(defaultURL);
    if (isInferenceApiConnected) {
      await listModels();
    }
  }

  //Try to connect with default URL at startup
  onMount(() => connectToPixanoInference());

  const listModels = async () => {
    const availableModels = await api.listModels();

    const defaultPrompts = Object.fromEntries(
      Object.values(QuestionTypeEnum).map(
        (questionType) => [questionType, { content: "", as_system: true }], //TODO? give a default system prompt ?
      ),
    ) as QuestionGenerationSystemPrompts;

    const completionAvailableModelsName = availableModels
      .filter((model) => model.task === MultimodalImageNLPTask.CONDITIONAL_GENERATION)
      .map((model) => model.name);

    inferenceModels = completionAvailableModelsName.map((name) => ({ id: name, value: name }));
    completionModelsStore.update((currentList) =>
      mergeModelLists(completionAvailableModelsName, currentList, defaultPrompts),
    );
  };

  connectToPixanoInference().catch(() => {
    console.error("Can't connect to Pixano Inference API");
  });

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

<div class="flex flex-row gap-2">
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

  <!-- For some reason, some tailwind classes don't work on select -->
  <!-- Use style instead -->
  <select
    class="py-3 px-2 border rounded-lg border-gray-200 outline-none text-slate-800 grow"
    style="color: #1e293b; border-color: #e5e7eb;"
    bind:value={selectedModel}
  >
    <option value="" selected disabled>Select a model</option>
    {#each inferenceModels as { id, value }}
      <option value={id}>{value}</option>
    {/each}
  </select>

  <IconButton
    tooltipContent="Instantiate a model"
    disabled={!isInferenceApiConnected}
    on:click={handleOpenAddModelModal}
  >
    <Plus />
  </IconButton>
</div>
<svelte:window on:keydown={handleKeyDown} />

{#if showConnectModal}
  <ConnectModal
    {vqaSectionWidth}
    {defaultURL}
    bind:isConnected={isInferenceApiConnected}
    on:cancelConnect={handleCloseConnectModal}
    on:listModels={listModels}
  />
{/if}

{#if showAddModelModal}
  <AddModelModal
    {vqaSectionWidth}
    on:listModels={listModels}
    on:cancelAddModel={handleCloseAddModelModal}
  />
{/if}
