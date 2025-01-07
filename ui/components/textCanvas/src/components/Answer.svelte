<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  /* eslint-disable svelte/no-at-html-tags */

  import type { Message, TextSpan, TextSpanType } from "@pixano/core";
  import { createEventDispatcher } from "svelte";
  import { editorSelectionToTextSpan, htmlToTextSpans, textSpansToHtml } from "../lib";

  export let textSpans: TextSpan[] = [];
  export let colorScale: (value: string) => string;
  export let textSpanAttributes: TextSpanType | null = null;
  export let message: Message;

  const messageId = message.id;

  const dispatch = createEventDispatcher();

  $: richEditorContent = textSpansToHtml({ text: message.data.content, textSpans, colorScale });

  const mouseupListener = (
    e: MouseEvent & {
      currentTarget: EventTarget & HTMLDivElement;
    },
  ) => {
    textSpanAttributes = editorSelectionToTextSpan({ editableDiv: e.currentTarget, messageId });
  };

  const inputListener = (
    e: Event & {
      currentTarget: EventTarget & HTMLDivElement;
    },
  ) => {
    const newTextSpans = htmlToTextSpans({
      editableDiv: e.currentTarget,
      prevTextSpans: textSpans,
    });

    const newMessageContent = e.currentTarget.innerText;

    dispatch("messageContentChange", { messageId, newTextSpans, newMessageContent });
  };
</script>

<div
  on:mouseup={mouseupListener}
  on:input={inputListener}
  contenteditable="true"
  class="outline-none flex flex-row flex-wrap items-center"
  role="textbox"
  tabindex="0"
>
  {@html richEditorContent}
</div>
