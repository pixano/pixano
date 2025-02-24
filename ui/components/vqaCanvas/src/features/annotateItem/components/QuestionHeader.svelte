<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { Sparkles } from "lucide-svelte";
  import { createEventDispatcher } from "svelte";

  import CompletedQuestion from "../assets/icons/completed-question.png";
  import PendingQuestion from "../assets/icons/pending-question.png";
  import type { GenerateAnswerEvent } from "../types";

  export let questionId: string;
  export let questionNumber: number;
  export let isQuestionCompleted: boolean;

  const dispatch = createEventDispatcher();

  const handleGenerateAnswer = () => {
    const eventDetail: GenerateAnswerEvent = { questionId };
    dispatch("generateAnswer", eventDetail);
  };
</script>

<div class="flex flex-row justify-between items-center">
  <div class="flex flex-row gap-2 items-center">
    <img
      alt="Question state logo"
      src={isQuestionCompleted ? CompletedQuestion : PendingQuestion}
      class="w-8 h-8"
    />
    <h3 class="font-medium">Question #{questionNumber}</h3>
  </div>

  <button
    on:click={handleGenerateAnswer}
    class="p-2 rounded-full hover:bg-primary-light transition duration-300"
  >
    <Sparkles size={20} class="text-slate-700" />
  </button>
</div>
