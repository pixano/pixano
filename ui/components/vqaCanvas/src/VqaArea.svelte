<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { Message } from "@pixano/core";

  import { AddQuestionButton } from "./features/addQuestion/components";
  import { QuestionForm } from "./features/annotateItem/components";
  import { groupMessagesByNumber } from "./features/annotateItem/lib/utils";

  // Exports
  export let messages: Message[];

  $: messagesByNumber = groupMessagesByNumber(messages);
</script>

<div class="bg-white p-4 flex flex-col gap-4 h-full overflow-y-auto">
  <AddQuestionButton on:storeQuestion />
  {#each messagesByNumber as messages}
    <QuestionForm bind:messages on:answerContentChange />
  {/each}
</div>
