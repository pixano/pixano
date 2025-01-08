/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { TextSpan } from "@pixano/core";

type NodeTree =
  | {
      type: "text";
      content: string;
    }
  | {
      type: "annotation";
      annotationId: string;
      children: NodeTree[];
    };

const createNodeTree = (childNodes: NodeListOf<ChildNode>): NodeTree[] => {
  const nodes: NodeTree[] = [];

  for (const node of childNodes) {
    if (node.nodeType === Node.TEXT_NODE && node.textContent) {
      nodes.push({
        type: "text",
        content: node.textContent,
      });
    } else if (node.nodeType === Node.ELEMENT_NODE && node instanceof HTMLElement) {
      if (node.tagName.toLowerCase() === "span") {
        const annotationId = node.dataset.id;
        if (annotationId) {
          nodes.push({
            type: "annotation",
            annotationId,
            children: createNodeTree(node.childNodes),
          });
        }
      }
    }
  }

  return nodes;
};

const parseNodeTreeToAnnotations = (
  nodes: NodeTree[],
  startOffset: number = 0,
  prevTextSpans: TextSpan[],
): { annotations: TextSpan[]; endOffset: number; mention: string } => {
  const annotations: TextSpan[] = [];
  let currentOffset = startOffset;
  let mention = "";

  for (const node of nodes) {
    if (node.type === "text") {
      currentOffset += node.content.length;
      mention += node.content;
    } else {
      const {
        annotations: childAnnotations,
        endOffset,
        mention,
      } = parseNodeTreeToAnnotations(node.children, currentOffset, prevTextSpans);

      const prevTextSpan = prevTextSpans.find((ts) => ts.id === node.annotationId);

      if (!prevTextSpan) {
        throw new Error(`Annotation ${node.annotationId} not found in prevTextSpans`);
      }

      /* eslint-disable-next-line @typescript-eslint/no-unused-vars */
      const { ui, ...rest } = prevTextSpan;

      annotations.push(
        new TextSpan({
          ...rest,
          data: {
            ...rest.data,
            mention,
            spans_start: [currentOffset],
            spans_end: [endOffset - 1],
          },
        }),
      );

      annotations.push(...childAnnotations);
      currentOffset = endOffset;
    }
  }

  return { annotations, endOffset: currentOffset, mention };
};

export const htmlToTextSpans = ({
  editableDiv,
  prevTextSpans,
}: {
  editableDiv: HTMLElement;
  prevTextSpans: TextSpan[];
}) => {
  const tree = createNodeTree(editableDiv.childNodes);

  const { annotations: newTextSpans } = parseNodeTreeToAnnotations(tree, 0, prevTextSpans);

  return newTextSpans;
};
