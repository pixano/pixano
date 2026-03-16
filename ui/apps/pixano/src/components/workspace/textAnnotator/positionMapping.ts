/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { Node as PmNode } from "@tiptap/pm/model";

/**
 * Converts a character offset in the original text to a ProseMirror position.
 *
 * ProseMirror positions include structural tokens (paragraph boundaries),
 * so we walk through all text nodes and count characters to find the right PM pos.
 */
export function charOffsetToPmPos(doc: PmNode, charOffset: number): number {
  let counted = 0;

  // pos tracks the PM position as we walk through text nodes
  let result = -1;

  doc.descendants((node, pos) => {
    if (result !== -1) return false; // already found
    if (!node.isText) return;

    const text = node.text;
    if (counted + text.length >= charOffset) {
      result = pos + (charOffset - counted);
      return false;
    }
    counted += text.length;
  });

  // If charOffset is beyond all text, return end of doc
  if (result === -1) {
    result = doc.content.size;
  }

  return result;
}

/**
 * Converts a ProseMirror position to a character offset in the original text.
 *
 * Inverse of charOffsetToPmPos: walks text nodes and counts characters
 * until we reach the given PM position.
 */
export function pmPosToCharOffset(doc: PmNode, pmPos: number): number {
  let charOffset = 0;

  doc.descendants((node, pos) => {
    if (!node.isText) return;

    const text = node.text;
    const nodeStart = pos;
    const nodeEnd = pos + text.length;

    if (pmPos <= nodeEnd) {
      charOffset += Math.max(0, pmPos - nodeStart);
      return false;
    }

    charOffset += text.length;
  });

  return charOffset;
}
