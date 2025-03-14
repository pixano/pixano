/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { TextSpan } from "@pixano/core";

export const groupTextSpansByViewId = (textSpans: TextSpan[]) =>
  textSpans.reduce(
    (acc, span) => {
      const viewId = span.data.view_ref.id;
      if (!acc[viewId]) acc[viewId] = [];
      acc[viewId].push(span);
      return acc;
    },
    {} as Record<string, TextSpan[]>,
  );
