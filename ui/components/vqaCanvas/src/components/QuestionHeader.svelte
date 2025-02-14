<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import CompletedQuestion from "../assets/icons/completed-question.png";
  import PendingQuestion from "../assets/icons/pending-question.png";

  export let questionNumber: number;
  export let isQuestionCompleted: boolean;
</script>

<div class="flex flex-row gap-2 items-center">
  <img
    alt="Question state logo"
    src={isQuestionCompleted ? CompletedQuestion : PendingQuestion}
    class="w-8 h-8"
  />
  <h3 class="font-medium">Question #{questionNumber}</h3>
</div>
