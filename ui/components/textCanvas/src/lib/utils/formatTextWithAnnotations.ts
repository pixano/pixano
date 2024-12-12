import type { TextSpan } from "@pixano/core";
import { createHtmlTag } from "./createHtmlTag";

export const formatTextWithAnnotations = ({
  text,
  textSpans,
  colorScale,
}: {
  text: string;
  textSpans: TextSpan[];
  colorScale: (value: string) => string;
}) => {
  const splittedText = text.split(" ");

  for (const textSpan of textSpans) {
    const { spans_start, spans_end, item_ref, view_ref, entity_ref, source_ref } = textSpan.data;

    const metadata = {
      "item-ref-id": item_ref.id,
      "item-ref-name": item_ref.name,
      "view-ref-id": view_ref.id,
      "view-ref-name": view_ref.name,
      "entity-ref-id": entity_ref.id,
      "entity-ref-name": entity_ref.name,
      "source-ref-id": source_ref.id,
      "source-ref-name": source_ref.name,
    };

    const bgColor = colorScale(entity_ref.id);

    const { openTag, closeTag } = createHtmlTag({
      metadata,
      bgColor,
      hidden: textSpan.ui.displayControl?.hidden,
    });

    const span_start = spans_start[0];
    const span_end = spans_end[0];

    splittedText[span_start] = openTag + splittedText[span_start];
    splittedText[span_end] = splittedText[span_end] + closeTag;
  }

  return splittedText
    .map((chunk, index) => `<span data-index="${index.toString()}">${chunk}</span>`)
    .join(" ");
};
