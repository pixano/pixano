/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { Editor } from "@tiptap/core";

import { MARK_UPDATE_META } from "./extensions/ReadOnlyContent";
import { charOffsetToPmPos } from "./positionMapping";
import type { TextSpan } from "$lib/ui";
import { isLuminanceHigh } from "$lib/ui";

function getTextColor(bgColor: string): string {
  return isLuminanceHigh(bgColor) ? "black" : "white";
}

/**
 * Computes glued span ranges from a TextSpan's spans_start/spans_end arrays.
 * Merges consecutive spans that are ≤2 characters apart (word gluing).
 */
function getGluedRanges(textSpan: TextSpan): Array<{ start: number; end: number }> {
  const ranges: Array<{ start: number; end: number }> = [];
  const { spans_start, spans_end } = textSpan.data;

  for (let i = 0; i < spans_start.length; i++) {
    const start = spans_start[i];
    let end = spans_end[i];

    // Glue next span if it's the next word (≤2 chars gap)
    while (spans_start.length > i + 1 && spans_start[i + 1] - end <= 2) {
      end = spans_end[i + 1];
      i++;
    }

    ranges.push({ start, end });
  }

  return ranges;
}

/**
 * Applies text span marks to a Tiptap editor.
 *
 * Builds a single ProseMirror transaction that:
 * 1. Removes all existing textSpanMark marks
 * 2. Adds marks for each text span with computed styles
 */
export function applyTextSpanMarks(
  editor: Editor,
  textSpans: TextSpan[],
  colorScale: (value: string) => string,
): void {
  const { state } = editor;
  const markType = state.schema.marks.textSpanMark;
  if (!markType) return;

  let tr = state.tr;

  // 1. Remove all existing textSpanMark marks
  state.doc.descendants((node, pos) => {
    if (!node.isText) return;
    const marks = node.marks.filter((m) => m.type === markType);
    for (const mark of marks) {
      tr = tr.removeMark(pos, pos + node.nodeSize, mark);
    }
  });

  // 2. Add marks for each text span
  for (const textSpan of textSpans) {
    const bgColor = colorScale(textSpan.data.entity_id);
    const hidden = textSpan.ui.displayControl.hidden ?? false;
    const highlighted = textSpan.ui.displayControl.highlighted === "self";
    const textColor = getTextColor(bgColor);

    const ranges = getGluedRanges(textSpan);

    for (const range of ranges) {
      const from = charOffsetToPmPos(state.doc, range.start);
      const to = charOffsetToPmPos(state.doc, range.end);

      if (from < to) {
        const mark = markType.create({
          id: textSpan.id,
          entityId: textSpan.data.entity_id,
          bgColor,
          textColor,
          hidden,
          highlighted,
        });
        tr = tr.addMark(from, to, mark);
      }
    }
  }

  // Set meta so ReadOnlyContent allows this transaction
  tr.setMeta(MARK_UPDATE_META, true);

  editor.view.dispatch(tr);
}
