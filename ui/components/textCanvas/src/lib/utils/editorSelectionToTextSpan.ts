/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { TextSpanType } from "@pixano/core";

export const editorSelectionToTextSpan = ({
  editableDiv,
  messageId,
}: {
  editableDiv: HTMLElement;
  messageId: string;
}): TextSpanType | null => {
  const selection = window.getSelection();

  if (!selection?.rangeCount) {
    return null;
  }

  //TMP for lint -- should be used somwhere but not yet
  messageId;
  ////

  const selectedText = selection.toString();

  if (!selectedText) {
    return null;
  }

  const range = selection.getRangeAt(0);
  const preCaretRange = range.cloneRange();

  preCaretRange.selectNodeContents(editableDiv);
  preCaretRange.setEnd(range.startContainer, range.startOffset);

  const span_start = preCaretRange.toString().length;

  return {
    spans_start: [span_start],
    spans_end: [span_start + selectedText.length - 1],
    mention: selectedText,
  };
};
