<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  /* eslint-disable svelte/no-at-html-tags */

  import { editorSelectionToTextSpan } from "./editorSelectionToTextSpan";
  import { textSpansToHtml } from "./textSpansToHtml";
  import type { TextSpan, TextSpanData, TextView } from "$lib/ui";

  interface Props {
    textSpans?: TextSpan[];
    colorScale: (value: string) => string;
    textSpanAttributes?: TextSpanData | null;
    textView: TextView;
    onSpanClick?: (textSpan: TextSpan) => void;
  }

  let {
    textSpans = [],
    colorScale,
    textSpanAttributes = $bindable(null),
    textView,
    onSpanClick,
  }: Props = $props();

  function escapeHtmlTagsOnly(text: string): string {
    return text.replace(/<\/?[a-zA-Z][^<>]*?>/g, (match) => {
      return match.replace("<", "-").replace(">", "-");
    });
  }

  let richEditorContent = $derived(
    textSpansToHtml({
      text: escapeHtmlTagsOnly(textView.data.content),
      textSpans,
      colorScale,
    }),
  );

  const mouseupListener = (
    e: MouseEvent & {
      currentTarget: EventTarget & HTMLDivElement;
    },
  ) => {
    textSpanAttributes = editorSelectionToTextSpan(e.currentTarget, textView.table_info.name);
  };

  const clickHandler = (event: MouseEvent) => {
    const target = event.target as HTMLElement;
    if (target && target.dataset.id) {
      const selectedTextSpan = textSpans.find((ts) => ts.id === target.dataset.id);
      if (selectedTextSpan) {
        onSpanClick?.(selectedTextSpan);
      }
    }
  };
</script>

<div
  onmouseup={mouseupListener}
  onmousedown={clickHandler}
  class="border rounded-lg p-2 whitespace-pre-wrap"
  role="textbox"
  tabindex="0"
>
  {@html richEditorContent}
</div>
