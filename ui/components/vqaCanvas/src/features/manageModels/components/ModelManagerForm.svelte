<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { Settings } from "lucide-svelte";

  import { IconButton, MessageTypeEnum, QuestionTypeEnum } from "@pixano/core";
  import { inferenceServerStore, vqaModels } from "@pixano/core/src/lib/stores/inferenceStore";

  import {
    completionModelsStore,
    type MessageGenerationPrompts,
    type PromptByQuestionType,
  } from "../../../stores/completionModels";
  import { mergeModelLists } from "../../../utils/mergeModelsList";
  import { DEFAULT_QUESTION_PROMPT, DEFAULT_TEMPERATURE } from "../defaults";
  import ConfigurePromptModal from "./ConfigurePromptModal.svelte";

  export let vqaSectionWidth: number;

  let selectedModel: string;
  let showPromptModal = false;

  // Build model dropdown options from centralized store
  $: inferenceModels = $vqaModels.map((m) => ({ id: m.name, value: m.name }));

  // When model selected, update completionModelsStore
  $: completionModelsStore.update((models) =>
    models.map((model) =>
      model.name === selectedModel ? { ...model, selected: true } : { ...model, selected: false },
    ),
  );

  // Auto-select first model when none is selected
  $: if (!selectedModel && inferenceModels.length >= 1) {
    selectedModel = inferenceModels[0].id;
  }

  // Sync available VQA models into completionModelsStore
  $: {
    const completionAvailableModelsName = $vqaModels.map((model) => model.name);

    if (completionAvailableModelsName.length > 0) {
      const defaultPromptsQuestion = Object.fromEntries(
        Object.values(QuestionTypeEnum).map((questionType) => [
          questionType,
          DEFAULT_QUESTION_PROMPT,
        ]),
      ) as PromptByQuestionType;

      const defaultPromptOthers = Object.fromEntries(
        Object.values(QuestionTypeEnum).map((questionType) => [questionType, ""]),
      ) as PromptByQuestionType;

      const prompts: MessageGenerationPrompts = {
        ...Object.fromEntries(
          Object.values(MessageTypeEnum).map((key) => [key, defaultPromptOthers]),
        ),
        [MessageTypeEnum.QUESTION]: defaultPromptsQuestion,
        as_system: true,
      } as MessageGenerationPrompts;

      completionModelsStore.update((currentList) =>
        mergeModelLists(completionAvailableModelsName, currentList, prompts, DEFAULT_TEMPERATURE),
      );
    }
  }
</script>

{#if !$inferenceServerStore.connected}
  <p class="text-sm text-muted-foreground py-2">No inference server connected</p>
{:else if inferenceModels.length === 0}
  <p class="text-sm text-muted-foreground py-2">No VLM models available</p>
{:else}
  <div class="flex flex-row gap-2">
    <select
      class="py-3 px-2 border rounded-lg border-border outline-none text-foreground grow"
      bind:value={selectedModel}
    >
      <option value="" selected disabled>Select a model</option>
      {#each inferenceModels as { id, value }}
        <option value={id}>{value}</option>
      {/each}
    </select>

    <IconButton
      tooltipContent="Configure generation prompts and temperature"
      disabled={$completionModelsStore.length === 0}
      on:click={() => (showPromptModal = !showPromptModal)}
    >
      <Settings />
    </IconButton>
  </div>
{/if}

{#if showPromptModal}
  <ConfigurePromptModal {vqaSectionWidth} on:cancelPrompt={() => (showPromptModal = false)} />
{/if}
