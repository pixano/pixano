/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { TextSpanTypeWithViewName } from "$lib/ui";

export const editorSelectionToTextSpan = (
  editableDiv: HTMLElement,
  viewName: string,
): TextSpanTypeWithViewName | null => {
  const selection = window.getSelection();

  if (!selection?.rangeCount) {
    return null;
  }

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
    spans_end: [span_start + selectedText.length],
    mention: selectedText,
    view_name: viewName,
  } as TextSpanTypeWithViewName;
};
