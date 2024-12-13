<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import type { Message, TextSpan } from "@pixano/core";
  import { onMount } from "svelte";
  import { customJoiner, customSplitter, formatTextWithAnnotations } from "../lib/utils";

  export let message: Message;
  export let textSpans: TextSpan[];
  export let colorScale: (value: string) => string;
  export let span_start: number;
  export let span_end: number;
  export let selectedText: string;
  export let messageId: string;

  $: formattedAnswer = formatTextWithAnnotations({
    text: message.data.content,
    textSpans,
    colorScale,
  });

  onMount(() => {
    const editableDiv = document.getElementById(message.id);

    editableDiv.addEventListener("focusout", () => {
      message.data.content = editableDiv.innerHTML.replace(/<[^>]*>/g, "");
    });

    editableDiv.addEventListener("mousedown", (event) => {
      const target = event.target as HTMLElement;
      if (target && target.dataset.index) {
        span_start = parseInt(target.dataset.index);
        console.log("span start", span_start);
      }
    });

    editableDiv.addEventListener("mouseup", (event) => {
      const target = event.target as HTMLElement;
      if (target && target.dataset.index) {
        span_end = parseInt(target.dataset.index);
        console.log("span end", span_end);

        const splittedText = customSplitter(message.data.content);
        const splittedSelectedText = splittedText.slice(span_start, span_end + 1);
        selectedText = customJoiner(splittedSelectedText);

        messageId = message.id;
      }
    });
  });
</script>

<div>
  <div
    id={message.id}
    contenteditable="true"
    class="outline-none flex flex-row flex-wrap items-center"
  >
    {@html formattedAnswer}
  </div>
</div>
