import type { NamedEntity } from "@pixano/core";
import { createHtmlTag } from "./createHtmlTag";

export const formatTextWithAnnotations = ({
  text,
  namedEntities,
  colorScale,
}: {
  text: string;
  namedEntities: NamedEntity[];
  colorScale: (value: string) => string;
}) => {
  const splittedText = text.split(" ");

  for (const namedEntity of namedEntities) {
    const { startIndex, endIndex, item_ref, view_ref, entity_ref, source_ref } = namedEntity.data;

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

    const { openTag, closeTag } = createHtmlTag({ metadata, bgColor });

    splittedText[startIndex] = openTag + splittedText[startIndex];
    splittedText[endIndex] = splittedText[endIndex] + closeTag;
  }

  return splittedText.join(" ");
};
