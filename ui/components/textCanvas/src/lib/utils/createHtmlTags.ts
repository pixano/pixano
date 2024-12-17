/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

export const createHtmlTags = ({
  metadata,
  bgColor,
  hidden,
  tagName = "span",
}: {
  metadata: Record<string, string>;
  bgColor: string;
  hidden: boolean;
  tagName?: string;
}) => {
  let openTag = `<${tagName}`;

  for (const [key, value] of Object.entries(metadata)) {
    openTag += ` data-${key}="${value}"`;
  }

  if (!hidden) {
    openTag += ` class="text-white rounded-md px-1 py-px mx-px" style="background:${hidden ? "transparent" : bgColor};"`;
  }

  openTag += `>`;

  const closeTag = `</${tagName}>`;

  return { openTag, closeTag };
};
