<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import type { Message, TextSpan } from "@pixano/core";
  import { onMount } from "svelte";
  import { formatTextWithAnnotations } from "../lib/utils";

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

        selectedText = message.data.content
          .split(" ")
          .slice(span_start, span_end + 1)
          .join(" ");

        messageId = message.id;
      }
    });
  });
</script>

<div>
  <div
    id={message.id}
    contenteditable="true"
    class="outline-none flex flex-row flex-wrap space-x-1 items-center"
  >
    {@html formattedAnswer}
  </div>
</div>
