/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

const TAG_NAME = "span";

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
  element.style.color = "white";
  element.style.padding = "1px 4px";
  element.style.borderRadius = "6px";
  element.style.margin = "0px 1px";

  element.innerText = content;

  if (hidden) {
    element.style.backgroundColor = "transparent";
  }

  for (const [key, value] of Object.entries(metadata)) {
    element.dataset[key] = value;
  }

  return element.outerHTML;
};
