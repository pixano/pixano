<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { Message } from "@pixano/core";

  import { QuestionForm } from "./components";
  import { groupMessagesByNumber } from "./lib/utils";
  import AddQuestionButton from "./components/addQuestion/AddQuestionButton.svelte";

  // Exports
  export let messages: Message[];

  $: messagesByNumber = groupMessagesByNumber(messages);
</script>

<div class="bg-white p-4 flex flex-col gap-4 h-full overflow-y-auto">
  <AddQuestionButton />
  {#each messagesByNumber as messages}
    <QuestionForm bind:messages on:answerContentChange />
  {/each}
</div>
