<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import {
    Message,
    SaveShapeType,
    TextSpan,
    type ImagesPerView,
    type Shape,
    type TextSpanType,
  } from "@pixano/core";
  import { Answer } from "./components";
  import { groupTextSpansByMessageId } from "./lib";

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
</script>

<div class="bg-white p-2 flex flex-col gap-2 h-full overflow-y-auto">
  <button class="bg-primary text-white p-2 rounded-md w-fit" on:click={onTagText} id="tagButton"
    >Tag Selected Text</button
  >
  {#each messages as message}
    <Answer
      {message}
      {colorScale}
      textSpans={spansByMessageId[message.id]}
      bind:textSpanAttributes
    />
  {/each}
</div>
