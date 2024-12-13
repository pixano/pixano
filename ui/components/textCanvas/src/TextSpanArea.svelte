<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import {
    cn,
    Message,
    MessageTypeEnum,
    SaveShapeType,
    TextSpan,
    type ImagesPerView,
    type Shape,
  } from "@pixano/core";
  import { Answer } from "./components";
  import Question from "./components/Question.svelte";

  // Exports
  export let selectedItemId: string;
  export let newShape: Shape;
  export let colorScale: (value: string) => string;
  export let textSpans: TextSpan[];
  export let messages: Message[];
  export let imagesPerView: ImagesPerView;

  // console.log("XXX textSpanArea", textSpans);
  // console.log("XXX messages", messages);
  // console.log("XXX imagesPerView", imagesPerView);

  const viewRef = { id: imagesPerView.images[0].id, name: "images" };

  let span_start: number | null = null;
  let span_end: number | null = null;
  let selectedText: string;
  let messageId: string;

  $: spansByMessage = textSpans.reduce(
    (acc, span) => {
      const messageId = span.data.annotation_ref.id;
      if (!acc[messageId]) acc[messageId] = [];
      acc[messageId].push(span);
      return acc;
    },
    {} as Record<string, TextSpan[]>,
  );

  const handleClick = () => {
    console.log("XXX handleClick", span_start, span_end, selectedText, messageId);
    if (span_start === null || span_end === null) return;

    newShape = {
      viewRef,
      itemId: selectedItemId,
      imageWidth: 0,
      imageHeight: 0,
      status: "saving",
      type: SaveShapeType.textSpan,
      attrs: {
        annotation_ref: { id: messageId, name: "messages" },
        spans_start: [span_start],
        spans_end: [span_end],
        mention: selectedText,
      },
    };

    span_start = null;
    span_end = null;
  };
</script>

<div class={cn("bg-white p-2 flex flex-col gap-2 h-full overflow-y-auto")}>
  <button
    class={cn("bg-primary text-white p-2 rounded-md w-fit")}
    on:click={handleClick}
    id="tagButton">Tag Selected Text</button
  >
  {#each messages.sort((a, b) => a.data.number - b.data.number) as message}
    {#if message.data.type === MessageTypeEnum.QUESTION}
      <Question {message} />
    {:else}
      <Answer
        {message}
        textSpans={spansByMessage[message.id]}
        {colorScale}
        bind:span_start
        bind:span_end
        bind:selectedText
        bind:messageId
      />
    {/if}
  {/each}
</div>
