/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { TextSpan } from "@pixano/core";
import type { HTMLTextSpanDataAttributes } from "../types";
import { htmlToString } from "./htmlToString";

const getSpanIndexInParent = (spanElement: HTMLSpanElement, parentElement: HTMLElement) => {
  const indexOfSpanInParent = parentElement.innerHTML.indexOf(spanElement.outerHTML);
  const htmlBeforeSpan = parentElement.innerHTML.substring(0, indexOfSpanInParent);

  const textBeforeSpan = htmlToString(htmlBeforeSpan);
  const span_start = textBeforeSpan.length;

  return span_start;
};

export const getAnnotationsFromHtml = ({
  editableDiv,
  textSpans,
}: {
  editableDiv: HTMLElement;
  textSpans: TextSpan[];
}) => {
  const newTextSpans: TextSpan[] = [];
  const htmlSpanTags = editableDiv.querySelectorAll("span");

  for (const spanElement of htmlSpanTags) {
    const mention = spanElement.textContent ?? "";

    if (mention.trim() === "") {
      continue;
    }

    const span_start = getSpanIndexInParent(spanElement, editableDiv);
    const span_end = span_start + mention.length - 1;

    const { id: textSpanId } = spanElement.dataset as HTMLTextSpanDataAttributes;

    const prevTextSpan = textSpans.find((textSpan) => textSpan.id === textSpanId);

    if (!prevTextSpan) {
      continue;
    }

    const textSpanData = {
      ...prevTextSpan.data,
      spans_start: [span_start],
      spans_end: [span_end],
      mention,
    };

    /* eslint-disable-next-line @typescript-eslint/no-unused-vars */
    const { ui, ...rest } = prevTextSpan;

    newTextSpans.push(new TextSpan({ ...rest, data: textSpanData }));
  }

  return newTextSpans;
};
