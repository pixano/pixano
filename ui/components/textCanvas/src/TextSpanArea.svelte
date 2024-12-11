<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { cn, TextSpan, SaveShapeType, type Shape } from "@pixano/core";
  import { onMount } from "svelte";
  import { formatTextWithAnnotations } from "./lib/utils";

  // Exports
  export let selectedItemId: string;
  export let newShape: Shape;
  export let colorScale: (value: string) => string;
  export let textSpans: TextSpan[];

  let answer = "This is some editable text. Select any text and tag it with custom metadata!";

  let startIndex: number | null = null;
  let endIndex: number | null = null;

  $: formattedAnswer = formatTextWithAnnotations({
    text: answer,
    textSpans,
    colorScale,
  });

  let viewRef = { id: "", name: "text" };

  onMount(() => {
    const editableDiv = document.getElementById("content");

    editableDiv.addEventListener("focusout", () => {
      answer = editableDiv.innerHTML.replace(/<[^>]*>/g, "");
    });

    editableDiv.addEventListener("mousedown", (event) => {
      const target = event.target as HTMLElement;
      if (target && target.dataset.index) {
        startIndex = parseInt(target.dataset.index);
      }
    });
    editableDiv.addEventListener("mouseup", (event) => {
      const target = event.target as HTMLElement;
      if (target && target.dataset.index) {
        endIndex = parseInt(target.dataset.index);
      }
    });
  });

  const handleClick = () => {
    if (startIndex === null || endIndex === null) return;

    const selectedText = answer
      .split(" ")
      .slice(startIndex, endIndex + 1)
      .join(" ");

    newShape = {
      viewRef,
      itemId: selectedItemId,
      imageWidth: 0,
      imageHeight: 0,
      status: "saving",
      type: SaveShapeType.textSpan,
      attrs: {
        startIndex,
        endIndex,
        content: selectedText,
      },
    };

    startIndex = null;
    endIndex = null;
  };
</script>

<div class={cn("bg-white p-2 flex flex-col gap-2 h-full")}>
  <button
    class={cn("bg-primary text-white p-2 rounded-md w-fit")}
    on:click={handleClick}
    id="tagButton">Tag Selected Text</button
  >
  <div
    id="content"
    contenteditable="true"
    class="outline-none flex flex-row flex-wrap space-x-1 items-center"
  >
    {@html formattedAnswer}
  </div>
</div>
