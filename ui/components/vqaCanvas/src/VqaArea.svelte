<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { Message, MessageTypeEnum } from "@pixano/core";
  import { Answer } from "./components";
  import Question from "./components/Question.svelte";

  // Exports
  export let messages: Message[];
</script>

<div class="bg-white p-2 flex flex-col gap-2 h-full overflow-y-auto">
  {#each messages.sort((a, b) => a.data.number - b.data.number) as message}
    {#if message.data.type === MessageTypeEnum.QUESTION}
      <Question {message} />
    {:else}
      <Answer {message} on:messageContentChange />
    {/if}
  {/each}
</div>
