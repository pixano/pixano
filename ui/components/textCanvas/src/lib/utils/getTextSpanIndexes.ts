export const getTextSpanIndexes = ({
  selection,
  text,
}: {
  selection: Selection;
  text: string;
}) => {
  const startOffset = Math.min(selection.anchorOffset, selection.focusOffset);
  const endOffset = Math.max(selection.anchorOffset, selection.focusOffset);

  const textBeforeSelection = text.slice(0, startOffset);
  const textAfterSelection = text.slice(0, endOffset);

  const startIndex = textBeforeSelection.split(" ").length - 1;
  const endIndex = textAfterSelection.split(" ").length - 1;

  return { startIndex, endIndex };
};
