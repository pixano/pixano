<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { Sparkles } from "lucide-svelte";

  import {
    LoadingModal,
    MultimodalImageNLPTask,
    PrimaryButton,
    QuestionTypeEnum,
  } from "@pixano/core";
  import { pixanoInferenceModelsStore } from "@pixano/core/src/lib/types/inference/modelsStore";

  // To refacto : Cross module imports
  import { generateQuestion } from "../../../../../datasetItemWorkspace/src/lib/stores/mutations/generateQuestion";
  import { default as QuestionTypeSelect } from "./AddQuestionModalTypeSelect.svelte";
  import NewQuestionForm from "./NewQuestionForm.svelte";

  export let vqaSectionWidth: number;

  let questionType: QuestionTypeEnum;
  let questionChoices: string[] = [];
  let questionContent: string = "";
  let isGenerating: boolean = false;

  $: completionModel = $pixanoInferenceModelsStore.find(
    (m) => m.task === MultimodalImageNLPTask.CONDITIONAL_GENERATION && m.selected,
  )?.name;

  const handleGenerateQuestion = async () => {
    if (!completionModel || completionModel.length === 0) return;
    isGenerating = true;
    const generatedQuestion = await generateQuestion(completionModel);
    isGenerating = false;

    if (!generatedQuestion) return;

    questionContent = generatedQuestion.content;
    questionChoices = generatedQuestion.choices;
  };
</script>

<!-- stop propagation to prevent from closing the modal when clicking on the background -->
<!-- svelte-ignore a11y-click-events-have-key-events -->
<!-- svelte-ignore a11y-no-static-element-interactions -->
<div
  on:click|stopPropagation={() => {}}
  class="fixed top-[calc(80px+5px)] z-50 overflow-y-auto w-68 rounded-md bg-white text-slate-800 flex flex-col gap-3 item-center pb-3 max-h-[calc(100vh-80px-10px)]"
  style={`left: calc(${vqaSectionWidth}px + 10px);`}
>
  <div class="bg-primary p-3 rounded-b-none rounded-t-md text-white">
    <p>QA editor</p>
  </div>
  <QuestionTypeSelect bind:questionType />

  <div class="flex flex-col gap-2 px-3">
    <PrimaryButton
      disabled={questionType === undefined || completionModel === ""}
      on:click={handleGenerateQuestion}
    >
      <Sparkles size={20} />Generate
    </PrimaryButton>
  </div>

  {#if questionType !== undefined}
    <NewQuestionForm {questionType} bind:questionChoices bind:questionContent on:storeQuestion />
  {/if}
</div>
{#if isGenerating}
  <LoadingModal />
{/if}
