/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

const TAG_NAME = "span";

function getTextColor(backgroundColor: string): string {
  //compute background color luminance to choose either white or black font color
  const hex = backgroundColor.replace(/^#/, "");
  const r = parseInt(hex.substring(0, 2), 16);
  const g = parseInt(hex.substring(2, 4), 16);
  const b = parseInt(hex.substring(4, 6), 16);

  const luminance = 0.2126 * r + 0.7152 * g + 0.0722 * b;

  return luminance > 128 ? "black" : "white";
}

export const createHtmlTags = ({
  content,
  metadata,
  bgColor,
  hidden,
}: {
  content: string;
  metadata: Record<string, string>;
  bgColor: string;
  hidden: boolean;
}) => {
  const element = document.createElement(TAG_NAME);

  element.style.backgroundColor = bgColor;
  element.style.color = getTextColor(bgColor);
  element.style.padding = "1px 4px";
  element.style.borderRadius = "6px";
  element.style.margin = "0px 1px";

  element.innerText = content;

  if (hidden) {
    element.style.backgroundColor = "transparent";
    element.style.color = "black";
  }

  for (const [key, value] of Object.entries(metadata)) {
    element.dataset[key] = value;
  }

  return element.outerHTML;
};
