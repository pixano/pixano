<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  /* eslint-disable svelte/no-at-html-tags */

  import type { Message, TextSpan, TextSpanType } from "@pixano/core";

  import { editorSelectionToTextSpan, textSpansToHtml } from "../lib";

  export let textSpans: TextSpan[] = [];
  export let colorScale: (value: string) => string;
  export let textSpanAttributes: TextSpanType | null = null;
  export let message: Message;

  const messageId = message.id;

  $: richEditorContent = textSpansToHtml({ text: message.data.content, textSpans, colorScale });

  const mouseupListener = (
    e: MouseEvent & {
      currentTarget: EventTarget & HTMLDivElement;
    },
  ) => {
    textSpanAttributes = editorSelectionToTextSpan({ editableDiv: e.currentTarget, messageId });
  };
</script>

<div on:mouseup={mouseupListener} class="border rounded-lg p-2" role="textbox" tabindex="0">
  {@html richEditorContent}
</div>
