export const createHtmlTag = ({
  metadata,
  bgColor,
  tagName = "span",
}: {
  metadata: Record<string, string>;
  bgColor: string;
  tagName?: string;
}) => {
  let openTag = `<${tagName}`;

  for (const [key, value] of Object.entries(metadata)) {
    openTag += ` data-${key}="${value}"`;
  }
  openTag += ` class="text-white rounded-md p-1" style="background:${bgColor}">`;

  const closeTag = `</${tagName}>`;

  return { openTag, closeTag };
};
