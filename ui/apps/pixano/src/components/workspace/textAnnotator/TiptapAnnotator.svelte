<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { Editor } from "@tiptap/core";
  import { StarterKit } from "@tiptap/starter-kit";

  import { applyTextSpanMarks } from "./applyTextSpanMarks";
  import { ReadOnlyContent } from "./extensions/ReadOnlyContent";
  import { TextSpanMark } from "./extensions/TextSpanMark";
  import { pmPosToCharOffset } from "./positionMapping";
  import type { TextSpan, TextSpanTypeWithViewName, TextView } from "$lib/ui";

  interface Props {
    textSpans?: TextSpan[];
    colorScale: (value: string) => string;
    textView: TextView;
    onSelectionChange?: (attrs: TextSpanTypeWithViewName) => void;
    onSpanClick?: (id: string) => void;
  }

  let { textSpans = [], colorScale, textView, onSelectionChange, onSpanClick }: Props = $props();

  let editorElement: HTMLDivElement | undefined = $state(undefined);
  let editor: Editor | undefined = $state(undefined);

  // Create editor when element is bound
  $effect(() => {
    if (!editorElement) return;

    const instance = new Editor({
      element: editorElement,
      extensions: [
        StarterKit.configure({
          blockquote: false,
          bulletList: false,
          codeBlock: false,
          heading: false,
          horizontalRule: false,
          listItem: false,
          orderedList: false,
        }),
        TextSpanMark.configure({
          onSpanClick: (id: string) => onSpanClick?.(id),
        }),
        ReadOnlyContent,
      ],
      content: {
        type: "doc",
        content: [
          {
            type: "paragraph",
            content: [{ type: "text", text: textView.data.content }],
          },
        ],
      },
      editable: true,
      onSelectionUpdate: ({ editor: ed }) => {
        const { from, to, empty } = ed.state.selection;
        if (empty) return;

        const doc = ed.state.doc;
        const startOffset = pmPosToCharOffset(doc, from);
        const endOffset = pmPosToCharOffset(doc, to);
        const mention = ed.state.doc.textBetween(from, to, "");

        if (mention.length > 0) {
          onSelectionChange?.({
            spans_start: [startOffset],
            spans_end: [endOffset],
            mention,
            view_name: textView.table_info.name,
          });
        }
      },
    });

    editor = instance;

    return () => {
      instance.destroy();
      editor = undefined;
    };
  });

  // Apply marks when textSpans or colorScale change
  $effect(() => {
    if (!editor) return;
    // Access reactive deps
    const spans = textSpans;
    const scale = colorScale;
    applyTextSpanMarks(editor, spans, scale);
  });
</script>

<div bind:this={editorElement} class="border rounded-lg p-2 whitespace-pre-wrap"></div>
