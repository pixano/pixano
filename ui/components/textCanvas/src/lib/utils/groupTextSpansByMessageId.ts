/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { TextSpan } from "@pixano/core";

export const groupTextSpansByMessageId = (textSpans: TextSpan[]) =>
  textSpans.reduce(
    (acc, span) => {
      const messageId = span.data.annotation_ref.id;
      if (!acc[messageId]) acc[messageId] = [];
      acc[messageId].push(span);
      return acc;
    },
    {} as Record<string, TextSpan[]>,
  );
