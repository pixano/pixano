<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { Plus, Settings, Sparkles } from "lucide-svelte";

  import {
    api,
    IconButton,
    MessageTypeEnum,
    MultimodalImageNLPTask,
    QuestionTypeEnum,
  } from "@pixano/core";

  import {
    completionModelsStore,
    type MessageGenerationPrompts,
    type PromptByQuestionType,
  } from "../../../stores/completionModels";
  import { mergeModelLists } from "../../../utils/mergeModelsList";
  import { DEFAULT_QUESTION_PROMPT, DEFAULT_TEMPERATURE, DEFAULT_URL } from "../defaults";
  import AddModelModal from "./AddModelModal.svelte";
  import ConfigurePromptModal from "./ConfigurePromptModal.svelte";
  import ConnectModal from "./ConnectModal.svelte";

  export let vqaSectionWidth: number;

  let selectedModel: string;

  let url = DEFAULT_URL;
  let isInferenceApiConnected = false;
  let inferenceModels: { id: string; value: string }[] = [];

  let showConnectModal = false;
  let showAddModelModal = false;
  let showPromptModal = false;

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
    isInferenceApiConnected = await api.isInferenceApiHealthy(url);
    if (isInferenceApiConnected) {
      await listModels();
    } else return Promise.reject(new Error(`Unable to connect to Pixano Inference at ${url}`));
  }

  const listModels = async () => {
    const availableModels = await api.listModels();

    const defaultPromptsQuestion = Object.fromEntries(
      Object.values(QuestionTypeEnum).map((questionType) => [
        questionType,
        DEFAULT_QUESTION_PROMPT,
      ]),
    ) as PromptByQuestionType;

    const defaultPromptOthers = Object.fromEntries(
      Object.values(QuestionTypeEnum).map((questionType) => [questionType, ""]),
    ) as PromptByQuestionType;

    //default prompts
    const prompts: MessageGenerationPrompts = {
      ...Object.fromEntries(
        Object.values(MessageTypeEnum).map((key) => [key, defaultPromptOthers]),
      ),
      [MessageTypeEnum.QUESTION]: defaultPromptsQuestion, // Manually set AFTER to avoid overwrite
      as_system: true,
    } as MessageGenerationPrompts;

    const completionAvailableModelsName = availableModels
      .filter((model) => model.task === MultimodalImageNLPTask.CONDITIONAL_GENERATION)
      .map((model) => model.name);

    inferenceModels = completionAvailableModelsName.map((name) => ({ id: name, value: name }));
    completionModelsStore.update((currentList) =>
      mergeModelLists(completionAvailableModelsName, currentList, prompts, DEFAULT_TEMPERATURE),
    );
  };

  connectToPixanoInference().catch((err) => {
    console.warn(err);
  });

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
  <IconButton
    tooltipContent="Pixano Inference connection"
    on:click={() => (showConnectModal = !showConnectModal)}
  >
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
    class="py-3 px-2 border rounded-lg border-border outline-none text-foreground grow"
    style="color: #1e293b; border-color: #e5e7eb;"
    bind:value={selectedModel}
  >
    <option value="" selected disabled>Select a model</option>
    {#each inferenceModels as { id, value }}
      <option value={id}>{value}</option>
    {/each}
  </select>

  <IconButton
    tooltipContent={isInferenceApiConnected
      ? "Instantiate a model"
      : "Pixano Inference is not connected"}
    disabled={!isInferenceApiConnected}
    on:click={() => (showAddModelModal = !showAddModelModal)}
  >
    <Plus />
  </IconButton>
  <IconButton
    tooltipContent="Configure generation prompts and temperature"
    disabled={$completionModelsStore.length === 0}
    on:click={() => (showPromptModal = !showPromptModal)}
  >
    <Settings />
  </IconButton>
</div>
<svelte:window on:keydown={handleKeyDown} />

{#if showConnectModal}
  <ConnectModal
    {vqaSectionWidth}
    {url}
    bind:isConnected={isInferenceApiConnected}
    on:cancelConnect={() => (showConnectModal = false)}
    on:listModels={listModels}
  />
{/if}

{#if showAddModelModal}
  <AddModelModal
    {vqaSectionWidth}
    on:listModels={listModels}
    on:cancelAddModel={() => (showAddModelModal = false)}
  />
{/if}

{#if showPromptModal}
  <ConfigurePromptModal {vqaSectionWidth} on:cancelPrompt={() => (showPromptModal = false)} />
{/if}
