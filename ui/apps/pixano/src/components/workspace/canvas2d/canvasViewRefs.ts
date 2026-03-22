/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { Reference } from "$lib/types/dataset";

export function resolveCanvasViewRef(
  viewName: string,
  loadedImageId: string | undefined,
  currentSequenceFrameRefsByView?: Record<string, Reference>,
): Reference {
  return currentSequenceFrameRefsByView?.[viewName] ?? { id: loadedImageId ?? "", name: viewName };
}
