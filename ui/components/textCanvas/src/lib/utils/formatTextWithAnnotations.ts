/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { TextSpan } from "@pixano/core";
import type { HTMLTextSpanDataAttributes } from "../types";
import { createHtmlTags } from "./createHtmlTags";
import { customJoiner, customSplitter } from "./customSplitter";

const getMetadataOfTextSpan = (textSpan: TextSpan): HTMLTextSpanDataAttributes => ({
  id: textSpan.id,
});

export const formatTextWithAnnotations = ({
  text,
  textSpans,
  colorScale,
}: {
  text: string;
  textSpans: TextSpan[];
  colorScale: (value: string) => string;
}) => {
  const splittedText = customSplitter(text);

  for (const textSpan of textSpans) {
    const { entity_ref, spans_start, spans_end } = textSpan.data;

    const metadata = getMetadataOfTextSpan(textSpan);

    const bgColor = colorScale(entity_ref.id);

    const { openTag, closeTag } = createHtmlTags({
      metadata,
      bgColor,
      hidden: textSpan.ui.displayControl?.hidden ?? false,
    });

    const span_start = spans_start[0];
    const span_end = spans_end[0];

    if (splittedText[span_start] && splittedText[span_end]) {
      splittedText[span_start] = openTag + splittedText[span_start];
      splittedText[span_end] = splittedText[span_end] + closeTag;
    }
  }

  return customJoiner(splittedText);
};
