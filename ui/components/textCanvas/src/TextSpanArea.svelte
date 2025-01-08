<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import {
    Message,
    MessageTypeEnum,
    SaveShapeType,
    TextSpan,
    type ImagesPerView,
    type Shape,
    type TextSpanType,
  } from "@pixano/core";
  import { Answer } from "./components";
  import Question from "./components/Question.svelte";
  import { createUpdatedMessage, groupTextSpansByMessageId } from "./lib";

  // Exports
  export let selectedItemId: string;
  export let newShape: Shape;
  export let colorScale: (value: string) => string;
  export let textSpans: TextSpan[];
  export let messages: Message[];
  export let imagesPerView: ImagesPerView;

  const viewRef = { id: imagesPerView.image[0].id, name: "images" };

  let textSpanAttributes: TextSpanType | null = null;

  $: spansByMessageId = groupTextSpansByMessageId(textSpans);

  const onTagText = () => {
    if (!textSpanAttributes) return;

    // Changing newShape opens the window for customizing and saving a new
    // anotation in the object inspector
    newShape = {
      viewRef,
      itemId: selectedItemId,
      imageWidth: 0,
      imageHeight: 0,
      status: "saving",
      type: SaveShapeType.textSpan,
      attrs: textSpanAttributes,
    };
  };

  const handleMessageContentChange = (event: CustomEvent) => {
    event.preventDefault();

    const { messageId, newTextSpans, newMessageContent } = event.detail as {
      messageId: string;
      newTextSpans: TextSpan[];
      newMessageContent: string;
    };

    const newSpansByMessageId = { ...spansByMessageId, [messageId]: newTextSpans };
    textSpans = Object.values(newSpansByMessageId).flat();

    messages = messages.map((message) =>
      message.id === messageId ? createUpdatedMessage({ message, newMessageContent }) : message,
    );
  };
</script>

<div class="bg-white p-2 flex flex-col gap-2 h-full overflow-y-auto">
  <button class="bg-primary text-white p-2 rounded-md w-fit" on:click={onTagText} id="tagButton"
    >Tag Selected Text</button
  >
  {#each messages.sort((a, b) => a.data.number - b.data.number) as message}
    {#if message.data.type === MessageTypeEnum.QUESTION}
      <Question {message} />
    {:else}
      <Answer
        {message}
        {colorScale}
        textSpans={spansByMessageId[message.id]}
        bind:textSpanAttributes
        on:messageContentChange={handleMessageContentChange}
      />
    {/if}
  {/each}
</div>
