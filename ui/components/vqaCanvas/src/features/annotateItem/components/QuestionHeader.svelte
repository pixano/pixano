<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { Sparkles } from "lucide-svelte";
  import { createEventDispatcher } from "svelte";

  import { messages } from "../../../../../datasetItemWorkspace/src/lib/stores/datasetItemWorkspaceStores";
  import { completionModelsStore } from "../../../stores/completionModels";
  import CompletedQuestion from "../assets/icons/completed-question.png";
  import PendingQuestion from "../assets/icons/pending-question.png";

  export let questionId: string;
  export let questionNumber: number;
  export let isQuestionCompleted: boolean;

  const dispatch = createEventDispatcher();

  const handleGenerateAnswer = () => {
    const question = $messages.find((m) => m.id === questionId);
    if (question === undefined) {
      console.error("ERROR: Message not found");
      return;
    }

    const completionModel =
      $completionModelsStore.filter((model) => model.selected)[0]?.name ?? undefined;
    if (completionModel === undefined) {
      console.error("ERROR: No model selected");
      return;
    }

    dispatch("generateAnswer", {
      questionId: question.id,
      completionModel,
    });
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
