<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { cn, NamedEntity, SaveShapeType, type ImagesPerView, type Shape } from "@pixano/core";
  import {
    formatTextWithAnnotations,
    getNamedEntityIndexes,
    getSelectedText,
    getSelection,
  } from "./lib/utils";

  // Exports
  export let selectedItemId: string;
  export let newShape: Shape;
  export let colorScale: (value: string) => string;
  export let namedEntities: NamedEntity[];

  let answer = "This is some editable text. Select any text and tag it with custom metadata!";
  $: formattedAnswer = formatTextWithAnnotations({
    text: answer,
    namedEntities,
    colorScale,
  });

  let viewRef = { id: "", name: "text" };

  const handleClick = () => {
    const selection = getSelection();
    const selectedText = getSelectedText(selection);

    const { startIndex, endIndex } = getNamedEntityIndexes({ selection, text: answer });

    newShape = {
      viewRef,
      itemId: selectedItemId,
      imageWidth: 0,
      imageHeight: 0,
      status: "saving",
      type: SaveShapeType.namedEntity,
      attrs: {
        startIndex,
        endIndex,
        content: selectedText,
      },
    };
  };
</script>

<div class={cn("bg-white p-2 flex flex-col gap-2 h-full")}>
  <button
    class={cn("bg-primary text-white p-2 rounded-md w-fit")}
    on:click={handleClick}
    id="tagButton">Tag Selected Text</button
  >

  <div id="content" contenteditable="true" class="h-full outline-none">
    {@html formattedAnswer}
  </div>
</div>
