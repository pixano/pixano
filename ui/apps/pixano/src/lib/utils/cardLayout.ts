/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { RecordPreview } from "$lib/types/dataset";

/**
 * Composition of a record card's media area, derived purely from the previews a
 * record carries — one rule for every dataset type, no workspace branching.
 */
export interface CardLayout {
  kind: "none" | "single" | "duo" | "many" | "imageText" | "textOnly";
  /** Image previews to render (1 for single/many, 2 for duo). */
  media: RecordPreview[];
  /** Text preview to render (imageText / textOnly). */
  text?: RecordPreview;
  /** Number of additional views not shown ("+N views" badge). */
  extraCount: number;
}

/** Decide how a record card composes its media area from the previews it has. */
export function cardLayout(previews: RecordPreview[]): CardLayout {
  const media = previews.filter((p) => p.kind === "image" && p.url !== "");
  const texts = previews.filter((p) => p.kind === "text");
  const text = texts[0];

  if (media.length === 0 && text) {
    return { kind: "textOnly", media: [], text, extraCount: previews.length - 1 };
  }
  if (media.length === 0) {
    return { kind: "none", media: [], extraCount: 0 };
  }
  if (text) {
    // Image + text (e.g. MEL): split card — primary image with the excerpt panel.
    return {
      kind: "imageText",
      media: media.slice(0, 1),
      text,
      extraCount: previews.length - 2,
    };
  }
  if (media.length === 1) {
    return { kind: "single", media, extraCount: 0 };
  }
  if (media.length === 2) {
    return { kind: "duo", media, extraCount: 0 };
  }
  // 3+ views (multi-camera): primary + "+N views" badge.
  return { kind: "many", media: media.slice(0, 1), extraCount: media.length - 1 };
}
