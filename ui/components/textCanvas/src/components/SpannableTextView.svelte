<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  /* eslint-disable svelte/no-at-html-tags */

  import type { TextSpan, TextSpanType, TextView } from "@pixano/core";

  import {
    getTopEntity,
    highlightObject,
  } from "../../../datasetItemWorkspace/src/lib/api/objectsApi";
  import { editorSelectionToTextSpan, textSpansToHtml } from "../lib";

  export let textSpans: TextSpan[] = [];
  export let colorScale: (value: string) => string;
  export let textSpanAttributes: TextSpanType | null = null;
  export let textView: TextView;

  $: richEditorContent = textSpansToHtml({ text: textView.data.content, textSpans, colorScale });

  const mouseupListener = (
    e: MouseEvent & {
      currentTarget: EventTarget & HTMLDivElement;
    },
  ) => {
    textSpanAttributes = editorSelectionToTextSpan(e.currentTarget, {
      id: textView.id,
      name: textView.table_info.name,
    });
  };

  const clickHandler = (event: MouseEvent) => {
    const target = event.target as HTMLElement;
    if (target && target.dataset.id) {
      const selectedTextSpan = textSpans.find((ts) => ts.id === target.dataset.id);
      if (selectedTextSpan) {
        highlightObject(getTopEntity(selectedTextSpan).id, false);
      }
    }
  };
</script>

<div
  on:mouseup={mouseupListener}
  on:mousedown={clickHandler}
  class="border rounded-lg p-2 whitespace-pre-wrap"
  role="textbox"
  tabindex="0"
>
  {@html richEditorContent}
</div>
