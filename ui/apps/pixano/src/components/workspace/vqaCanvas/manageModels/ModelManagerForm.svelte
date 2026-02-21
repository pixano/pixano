<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { untrack } from "svelte";
  import { Settings } from "lucide-svelte";

  import { MessageTypeEnum, QuestionTypeEnum } from "$lib/types/dataset";
  import type { InferenceModel, InferenceServerState } from "$lib/types/inference";
  import { IconButton } from "$lib/ui";
  import { effectProbe } from "$lib/utils/effectProbe";

  import {
    type PixanoInferenceCompletionModel,
    type MessageGenerationPrompts,
    type PromptByQuestionType,
  } from "$lib/stores/vqaStores.svelte";
  import { mergeModelLists } from "../utils/mergeModelsList";
  import { DEFAULT_QUESTION_PROMPT, DEFAULT_TEMPERATURE } from "./defaults";
  import ConfigurePromptModal from "./ConfigurePromptModal.svelte";

  interface Props {
    vqaSectionWidth: number;
    inferenceServer: InferenceServerState;
    vqaModels: InferenceModel[];
    completionModels: PixanoInferenceCompletionModel[];
    onCompletionModelsChange?: (models: PixanoInferenceCompletionModel[]) => void;
  }

  let { vqaSectionWidth, inferenceServer, vqaModels, completionModels, onCompletionModelsChange }: Props = $props();

  let selectedModel = $state("");
  let showPromptModal = $state(false);

  // Build model dropdown options from props
  let inferenceModels = $derived(vqaModels.map((m) => ({ id: m.name, value: m.name })));

  // When model selected, update completionModels via callback
  $effect(() => {
    const model = selectedModel;
    const models = inferenceModels;
    untrack(() => {
      effectProbe("ModelManagerForm.syncSelectedModel", {
        selectedModel: model,
        modelCount: models.length,
      });
      let hasSelectionChange = false;
      const nextModels = completionModels.map((m) => {
        const shouldSelect = m.name === model;
        if (m.selected === shouldSelect) return m;
        hasSelectionChange = true;
        return { ...m, selected: shouldSelect };
      });
      if (hasSelectionChange) onCompletionModelsChange?.(nextModels);
    });
  });

  // Auto-select first model when none is selected
  $effect(() => {
    const models = inferenceModels;
    untrack(() => {
      effectProbe("ModelManagerForm.autoselect", {
        selectedModel,
        modelCount: models.length,
      });
      if (!selectedModel && models.length >= 1) {
        selectedModel = models[0].id;
      }
    });
  });

  // Sync available VQA models into completionModels
  $effect(() => {
    const vqaModelsList = vqaModels;
    untrack(() => {
      effectProbe("ModelManagerForm.syncModelList", {
        modelCount: vqaModelsList.length,
      });
    });
    const completionAvailableModelsName = vqaModelsList.map((model) => model.name);

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

      const nextList = mergeModelLists(
        completionAvailableModelsName,
        completionModels,
        prompts,
        DEFAULT_TEMPERATURE,
      );
      const hasListChange =
        nextList.length !== completionModels.length ||
        nextList.some((model, index) => model !== completionModels[index]);
      if (hasListChange) onCompletionModelsChange?.(nextList);
    }
  });
</script>

{#if !inferenceServer.connected}
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
      disabled={completionModels.length === 0}
      onclick={() => (showPromptModal = !showPromptModal)}
    >
      <Settings />
    </IconButton>
  </div>
{/if}

{#if showPromptModal}
  <ConfigurePromptModal {vqaSectionWidth} onCancelPrompt={() => (showPromptModal = false)} />
{/if}
