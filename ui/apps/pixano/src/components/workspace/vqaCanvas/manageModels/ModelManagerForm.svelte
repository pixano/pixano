<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { Gear } from "phosphor-svelte";
  import { untrack } from "svelte";

  import { mergeModelLists } from "../utils/mergeModelsList";
  import ConfigurePromptModal from "./ConfigurePromptModal.svelte";
  import { DEFAULT_QUESTION_PROMPT, DEFAULT_TEMPERATURE } from "./defaults";
  import { selectedVqaModel } from "$lib/stores/inferenceStores.svelte";
  import {
    type MessageGenerationPrompts,
    type PixanoInferenceCompletionModel,
    type PromptByQuestionType,
  } from "$lib/stores/vqaStores.svelte";
  import { MessageTypeEnum, QuestionTypeEnum } from "$lib/types/dataset";
  import {
    formatInferenceProviderName,
    getInferenceModelKey,
    type InferenceModel,
    type InferenceServerState,
  } from "$lib/types/inference";
  import { IconButton } from "$lib/ui";
  import { effectProbe } from "$lib/utils/effectProbe";

  interface Props {
    vqaSectionWidth: number;
    inferenceServer: InferenceServerState;
    vqaModels: InferenceModel[];
    completionModels: PixanoInferenceCompletionModel[];
    onCompletionModelsChange?: (models: PixanoInferenceCompletionModel[]) => void;
  }

  let {
    vqaSectionWidth,
    inferenceServer,
    vqaModels,
    completionModels,
    onCompletionModelsChange,
  }: Props = $props();

  let selectedModel = $state("");
  let showPromptModal = $state(false);

  // Build model dropdown options from props
  let inferenceModels = $derived(
    vqaModels.map((m) => ({
      id: getInferenceModelKey(m),
      value: `${m.name} · ${formatInferenceProviderName(m.provider_name)}`,
      selection: { name: m.name, provider_name: m.provider_name },
    })),
  );

  // When model selected, update completionModels via callback
  $effect(() => {
    const model = selectedModel;
    const models = inferenceModels;
    untrack(() => {
      effectProbe("ModelManagerForm.syncSelectedModel", {
        selectedModel: model,
        modelCount: models.length,
      });
      if (!model) {
        selectedVqaModel.value = null;
        return;
      }
      let hasSelectionChange = false;
      const nextModels = completionModels.map((m) => {
        const shouldSelect = getInferenceModelKey(m) === model;
        if (m.selected === shouldSelect) return m;
        hasSelectionChange = true;
        return { ...m, selected: shouldSelect };
      });
      selectedVqaModel.value = models.find((entry) => entry.id === model)?.selection ?? null;
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
      const hasSelection = models.some((model) => model.id === selectedModel);
      if (hasSelection) return;
      const currentSelection = selectedVqaModel.value;
      const currentSelectionId = currentSelection ? getInferenceModelKey(currentSelection) : "";
      selectedModel = models.find((model) => model.id === currentSelectionId)?.id ?? models[0]?.id ?? "";
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
    const completionAvailableModels = vqaModelsList.map((model) => ({
      name: model.name,
      provider_name: model.provider_name,
    }));

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
      completionAvailableModels,
      completionModels,
      prompts,
      DEFAULT_TEMPERATURE,
    );
    const hasListChange =
      nextList.length !== completionModels.length ||
      nextList.some((model, index) => model !== completionModels[index]);
    if (hasListChange) onCompletionModelsChange?.(nextList);
    if (completionAvailableModels.length === 0) {
      selectedVqaModel.value = null;
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
      <Gear weight="regular" />
    </IconButton>
  </div>
{/if}

{#if showPromptModal}
  <ConfigurePromptModal
    {vqaSectionWidth}
    {completionModels}
    onCancelPrompt={() => (showPromptModal = false)}
  />
{/if}
