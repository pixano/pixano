/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { TextSpan } from "$lib/ui";

export const groupTextSpansByViewId = (textSpans: TextSpan[]) =>
  textSpans.reduce(
    (acc, span) => {
      const viewId = span.data.frame_id;
      if (!acc[viewId]) acc[viewId] = [];
      acc[viewId].push(span);
      return acc;
    },
    {} as Record<string, TextSpan[]>,
  );
