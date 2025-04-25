<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { Share2, Sparkles, Type } from "lucide-svelte";
  import { onMount } from "svelte";

  import {
    api,
    IconButton,
    ImageTask,
    MessageTypeEnum,
    MultimodalImageNLPTask,
    PrimaryButton,
    QuestionTypeEnum,
    WorkspaceType,
  } from "../..";
  import type { MessageGenerationPrompts, PromptByQuestionType } from "../..";
  import { currentDatasetStore } from "../../../../../apps/pixano/src/lib/stores/datasetStores";
  import { pixanoInferenceModelsStore } from "../../lib/types/inference/modelsStore";
  import { mergeModelLists } from "../../lib/utils/mergeModelsList";
  import ConnectModal from "./ConnectModal.svelte";
  import { DEFAULT_QUESTION_PROMPT, DEFAULT_TEMPERATURE, DEFAULT_URL } from "./defaults";
  import SelectModelModal from "./SelectModelModal.svelte";

  let url = DEFAULT_URL;
  let isInferenceApiConnected = false;

  let showConnectModal = false;
  let showVQASelectModal = false;
  let showMaskSelectModal = false;
  let selectedMaskModelName: string = "";
  let selectedVQAModelName: string = "";

  let isVQA = $currentDatasetStore.workspace === WorkspaceType.IMAGE_VQA;
  //let isVIDEO = $currentDatasetStore.workspace === WorkspaceType.VIDEO;

  const show = (modalName: string = "") => {
    showConnectModal = modalName === "connect";
    showMaskSelectModal = modalName === "mask";
    showVQASelectModal = modalName === "vqa";
  };

  onMount(() => {
    //Try to connect with default URL at startup
    connectToPixanoInference();
    //react to set first model of each task as selected if none selected and set selcted model names per task
    const unsubscribe = pixanoInferenceModelsStore.subscribe((models) => {
      const updatedModels = [...models];
      let changed = false;
      const selectedNames: Record<string, string> = {};
      const tasks = [ImageTask.MASK_GENERATION, MultimodalImageNLPTask.CONDITIONAL_GENERATION];
      for (const task of tasks) {
        const modelsOfTask = updatedModels.filter((m) => m.task === task);
        if (modelsOfTask.length === 0) continue;

        let selected = modelsOfTask.find((m) => m.selected);
        if (!selected) {
          modelsOfTask[0].selected = true;
          selected = modelsOfTask[0];
          changed = true;
        }

        selectedNames[task] = selected.name;
      }
      // Update names
      selectedMaskModelName = selectedNames[ImageTask.MASK_GENERATION] || "";
      selectedVQAModelName = selectedNames[MultimodalImageNLPTask.CONDITIONAL_GENERATION] || "";

      if (changed) {
        pixanoInferenceModelsStore.set(updatedModels);
      }
    });
    return () => unsubscribe();
  });

  async function connectToPixanoInference() {
    isInferenceApiConnected = await api.isInferenceApiHealthy(url);
    if (isInferenceApiConnected) {
      await listModels();
    }
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

    pixanoInferenceModelsStore.update((currentList) =>
      mergeModelLists(availableModels, currentList, prompts, DEFAULT_TEMPERATURE),
    );
  };

  connectToPixanoInference().catch(() => {
    console.error("Can't connect to Pixano Inference API");
  });

  const handleOpenConnectModal = (event: Event) => {
    // stopPropgation is not called as event modifier
    // because event modifiers can only be used on DOM elements
    event.stopPropagation();
    show(showConnectModal ? "" : "connect");
  };

  const handleKeyDown = (
    event: KeyboardEvent & {
      currentTarget: EventTarget & Window;
    },
  ) => {
    if (event.key === "Escape") {
      if ((event.target as Element)?.tagName === "INPUT") return event.preventDefault();
      show();
    }
  };
</script>

<div class="flex flex-row gap-2">
  <IconButton tooltipContent="Pixano Inference connection" on:click={handleOpenConnectModal}>
    <Sparkles size={20} class={isInferenceApiConnected ? "text-green-500" : "text-red-500"} />
  </IconButton>

  {#if isVQA}
    <PrimaryButton on:click={() => (showVQASelectModal = !showVQASelectModal)}>
      <Type />{selectedVQAModelName !== "" ? selectedVQAModelName : "VQA Model"}
    </PrimaryButton>
  {/if}
  <PrimaryButton on:click={() => (showMaskSelectModal = !showMaskSelectModal)}>
    <Share2 />{selectedMaskModelName !== "" ? selectedMaskModelName : "Mask Generation"}
  </PrimaryButton>
</div>
<svelte:window on:keydown={handleKeyDown} />

{#if showConnectModal}
  <ConnectModal
    {url}
    bind:isConnected={isInferenceApiConnected}
    on:cancelConnect={() => show()}
    on:listModels={listModels}
  />
{/if}

{#if showMaskSelectModal}
  <SelectModelModal
    task={ImageTask.MASK_GENERATION}
    {listModels}
    on:cancel={() => {
      showMaskSelectModal = false;
    }}
  />
{/if}
{#if showVQASelectModal}
  <SelectModelModal
    task={MultimodalImageNLPTask.CONDITIONAL_GENERATION}
    {listModels}
    on:cancel={() => {
      showVQASelectModal = false;
    }}
  />
{/if}
