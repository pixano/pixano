<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { Sparkles } from "lucide-svelte";

  import type { QuestionTypeEnum } from "@pixano/core";
  import PrimaryButton from "@pixano/core/src/components/ui/molecules/PrimaryButton.svelte";

  import { default as ModelSelect } from "./AddQuestionModalModelSelect.svelte";
  import { default as QuestionTypeSelect } from "./AddQuestionModalTypeSelect.svelte";
  import NewQuestionForm from "./NewQuestionForm.svelte";

  let questionType: QuestionTypeEnum;
  let completionModel: string;
  let questionChoices: string[] = [];
  let questionContent: string = "";

  const handleGenerateQuestion = () => {
    // TODO: generate question
    const mockResponse = {
      question: "What is the main object?",
      choices: ["A", "B", "C"],
    };

    questionChoices = mockResponse.choices;
    questionContent = mockResponse.question;
  };
</script>

<!-- stop propagation to prevent from closing the modal when clicking on the background -->
<!-- svelte-ignore a11y-click-events-have-key-events -->
<!-- svelte-ignore a11y-no-static-element-interactions -->
<div
  on:click|stopPropagation={() => {}}
  class="fixed top-[calc(80px+5px)] left-[calc(300px+5px)] z-50 overflow-y-auto w-68 rounded-md bg-white text-slate-800 flex flex-col gap-3 item-center pb-3 max-h-[calc(100vh-80px-10px)]"
>
  <div class="bg-primary p-3 rounded-b-none rounded-t-md text-white">
    <p>QA editor</p>
  </div>

  <QuestionTypeSelect bind:questionType />
  <ModelSelect bind:selectedModel={completionModel} />

  <div class="flex flex-col gap-2 px-3">
    <PrimaryButton
      isSelected
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
