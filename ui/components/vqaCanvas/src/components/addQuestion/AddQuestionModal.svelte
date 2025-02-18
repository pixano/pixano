<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { Sparkles } from "lucide-svelte";

  import type { QuestionTypeEnum } from "@pixano/core";
  import PrimaryButton from "@pixano/core/src/components/ui/molecules/PrimaryButton.svelte";

  import { default as Header } from "./AddQuestionModalHeader.svelte";
  import { default as ModelSelect } from "./AddQuestionModalModelSelect.svelte";
  import { default as QuestionTypeSelect } from "./AddQuestionModalTypeSelect.svelte";

  let questionType: QuestionTypeEnum;
  let completionModel: string;

  const handleGenerateQuestion = () => {
    // TODO: generate question
    console.log("generate question");
  };
</script>

<!-- stop propagation to prevent from closing the modal when clicking on the background -->
<!-- svelte-ignore a11y-click-events-have-key-events -->
<!-- svelte-ignore a11y-no-static-element-interactions -->
<div
  on:click|stopPropagation={() => {}}
  class="fixed top-[calc(80px+5px)] left-[calc(300px+5px)] z-50 overflow-y-auto w-60 rounded-md bg-white text-slate-800 flex flex-col item-center pb-3"
>
  <Header />
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
</div>
