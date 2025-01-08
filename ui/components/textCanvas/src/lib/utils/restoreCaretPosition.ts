/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

export const restoreCaretPosition = ({
  element,
  position,
}: {
  element: HTMLElement;
  position: number;
}) => {
  const range = document.createRange();
  const selection = window.getSelection();

  let currentPos = 0;
  let found = false;

  function traverse(node: Node) {
    if (found) return;

    if (node.nodeType === Node.TEXT_NODE) {
      const length = node.textContent?.length || 0;
      if (currentPos + length >= position) {
        range.setStart(node, position - currentPos);
        range.setEnd(node, position - currentPos);
        found = true;
      }
      currentPos += length;
    } else {
      for (const child of Array.from(node.childNodes)) {
        traverse(child);
      }
    }
  }

  traverse(element);

  if (selection && found) {
    selection.removeAllRanges();
    selection.addRange(range);
  }
};
