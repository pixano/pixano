/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

export interface PromptBoxLike {
  x: number;
  y: number;
  width: number;
  height: number;
}

export function toBoxPrompt(box: PromptBoxLike | null): number[][] | null {
  if (!box) return null;

  const x1 = Math.round(Math.min(box.x, box.x + box.width));
  const y1 = Math.round(Math.min(box.y, box.y + box.height));
  const x2 = Math.round(Math.max(box.x, box.x + box.width));
  const y2 = Math.round(Math.max(box.y, box.y + box.height));

  return [[x1, y1, x2, y2]];
}
