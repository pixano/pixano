/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { isLuminanceHigh } from "../../../../core/src/lib/utils/colorUtils";

const TAG_NAME = "span";

function getTextColor(backgroundColor: string): string {
  return isLuminanceHigh(backgroundColor) ? "black" : "white";
}

export const createHtmlTags = ({
  content,
  metadata,
  bgColor,
  hidden,
  highlighted,
}: {
  content: string;
  metadata: Record<string, string>;
  bgColor: string;
  hidden: boolean;
  highlighted: boolean;
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
  if (highlighted) {
    // glow effect + small outline
    element.style.boxShadow = `0 0 0 1px rgba(0, 0, 0, 0.2), 0 0 10px ${bgColor}`;
  }

  for (const [key, value] of Object.entries(metadata)) {
    element.dataset[key] = value;
  }

  return element.outerHTML;
};
