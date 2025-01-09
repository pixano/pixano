<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { Message, MessageTypeEnum } from "@pixano/core";
  import { Answer } from "./components";
  import Question from "./components/Question.svelte";
  import { createUpdatedMessage } from "./lib";

  // Exports
  export let messages: Message[];

  const handleMessageContentChange = (event: CustomEvent) => {
    event.preventDefault();

    const { messageId, newMessageContent } = event.detail as {
      messageId: string;
      newMessageContent: string;
    };

    messages = messages.map((message) =>
      message.id === messageId ? createUpdatedMessage({ message, newMessageContent }) : message,
    );
  };
</script>

<div class="bg-white p-2 flex flex-col gap-2 h-full overflow-y-auto">
  {#each messages.sort((a, b) => a.data.number - b.data.number) as message}
    {#if message.data.type === MessageTypeEnum.QUESTION}
      <Question {message} />
    {:else}
      <Answer {message} on:messageContentChange={handleMessageContentChange} />
    {/if}
  {/each}
</div>
