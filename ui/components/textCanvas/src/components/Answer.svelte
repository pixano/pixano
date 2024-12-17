<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import type { Message, TextSpan, TextSpanType } from "@pixano/core";
  import { createEventDispatcher, onDestroy, onMount } from "svelte";
  import {
    formatTextWithAnnotations,
    getAnnotationsFromHtml,
    getTextSpanAttributes,
    htmlToString,
  } from "../lib/utils";

  export let message: Message;
  export let textSpans: TextSpan[] = [];
  export let colorScale: (value: string) => string;
  export let textSpanAttributes: TextSpanType | null = null;

  const dispatch = createEventDispatcher();
  const messageId = message.id;

  let editableDiv: HTMLElement | null = null;

  $: formattedAnswer = formatTextWithAnnotations({
    text: message.data.content,
    textSpans,
    colorScale,
  });

  const mouseupListener = () => {
    if (!editableDiv) return;
    textSpanAttributes = getTextSpanAttributes({ editableDiv, messageId });
  };

  const keyupListener = () => {
    if (!editableDiv) return;

    const newTextSpans = getAnnotationsFromHtml({ editableDiv, textSpans });
    const newMessageContent = htmlToString(editableDiv.innerHTML);

    dispatch("messageContentChange", { messageId, newTextSpans, newMessageContent });
  };

  onMount(() => {
    editableDiv = document.getElementById(messageId);

    editableDiv?.addEventListener("mouseup", mouseupListener);
    editableDiv?.addEventListener("keyup", keyupListener);
  });

  onDestroy(() => {
    editableDiv?.removeEventListener("mouseup", mouseupListener);
    editableDiv?.removeEventListener("keyup", keyupListener);
  });
</script>

<div
  id={message.id}
  contenteditable="true"
  class="outline-none flex flex-row flex-wrap items-center"
>
  {@html formattedAnswer}
</div>
