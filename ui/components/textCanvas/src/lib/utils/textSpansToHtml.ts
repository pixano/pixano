/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { TextSpan } from "@pixano/core";

import type { HTMLTextSpanDataAttributes } from "../types";
import { createHtmlTags } from "./createHtmlTags";

/**
 * Position and HTML content of a text span
 */
interface SpanPosition {
  start: number;
  end: number;
  spanStart: number;
  spanEnd: number;
  html: string;
}

/**
 * Hierarchical structure of text spans
 */
interface SpanTree extends SpanPosition {
  textSpan: TextSpan | null;
  children: SpanTree[];
}

const CLOSING_TAG = "</span>";

const getMetadataOfTextSpan = (textSpan: TextSpan): HTMLTextSpanDataAttributes => ({
  id: textSpan.id,
});

const getTextSpanPosition = (
  text: string,
  textSpan: TextSpan,
  colorScale: (value: string) => string,
): SpanPosition => {
  const start = textSpan.data.spans_start[0];
  const end = textSpan.data.spans_end[0] + 1;
  const content = text.slice(start, end);

  const spanHtml = createHtmlTags({
    content,
    metadata: getMetadataOfTextSpan(textSpan),
    bgColor: colorScale(textSpan.data.entity_ref.id),
    hidden: textSpan.ui.displayControl?.hidden ?? false,
  });

  const spanEnd = spanHtml.length - CLOSING_TAG.length;
  const spanStart = spanEnd - content.length;

  return { start, end, spanStart, spanEnd, html: spanHtml };
};

const getHtmlFromTree = (tree: SpanTree): string => {
  if (tree.children.length === 0) {
    return tree.html;
  }

  const sortedChildren = [...tree.children].sort((a, b) => a.start - b.start);
  const treeContent = tree.html.slice(tree.spanStart, tree.spanEnd);

  let html = tree.textSpan ? tree.html.slice(0, tree.spanStart) : "";
  let currentPosition = 0;

  for (const child of sortedChildren) {
    if (currentPosition < child.start - tree.start) {
      html += treeContent.slice(currentPosition, child.start - tree.start);
    }
    html += getHtmlFromTree(child);

    currentPosition = child.end - tree.start;
  }

  const remainingContent =
    currentPosition < tree.end - tree.start ? treeContent.slice(currentPosition) : "";

  return html + remainingContent + (tree.textSpan ? CLOSING_TAG : "");
};

const buildSpanTree = ({
  text,
  textSpans,
  colorScale,
}: {
  text: string;
  textSpans: TextSpan[];
  colorScale: (value: string) => string;
}): SpanTree => {
  const tree: SpanTree = {
    start: 0,
    end: text.length,
    spanStart: 0,
    spanEnd: text.length,
    html: text,
    textSpan: null,
    children: [],
  };

  for (const textSpan of textSpans) {
    const spanPosition = getTextSpanPosition(text, textSpan, colorScale);
    let currentNode: SpanTree = tree;

    while (true) {
      const parentNode = currentNode.children.find(
        (node) => node.start <= spanPosition.start && node.end >= spanPosition.end,
      );

      if (!parentNode) {
        currentNode.children.push({ ...spanPosition, textSpan, children: [] });
        break;
      }
      currentNode = parentNode;
    }
  }

  return tree;
};

/**
 *
 * Converts an array of text spans into nested HTML span elements
 *
 * @param text - The original text content
 * @param textSpans - Array of text spans to convert
 * @param colorScale - Function to determine background color for each span
 *
 * @returns The HTML string with nested span elements
 *
 */
export const textSpansToHtml = ({
  text,
  textSpans,
  colorScale,
}: {
  text: string;
  textSpans: TextSpan[];
  colorScale: (value: string) => string;
}): string => {
  if (!text || !textSpans.length) {
    return text;
  }

  const sortedTextSpans = textSpans.sort((a, b) => {
    const aLength = a.data.spans_end[0] - a.data.spans_start[0];
    const bLength = b.data.spans_end[0] - b.data.spans_start[0];
    return bLength - aLength;
  });

  const spanTree = buildSpanTree({ text, textSpans: sortedTextSpans, colorScale });

  const html = getHtmlFromTree(spanTree);

  return html;
};
