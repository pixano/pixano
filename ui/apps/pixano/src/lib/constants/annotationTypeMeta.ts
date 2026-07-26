/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { Robot, Target, User } from "phosphor-svelte";

import { BaseSchema } from "$lib/types/dataset";

/**
 * Single source of truth for annotation-type / source / confidence badge styling.
 *
 * Per-type hues are DATA ENCODING (each annotation kind keeps a distinct, stable hue so
 * users can tell them apart at a glance) — they intentionally use literal hue classes.
 * STATE-meaning colors (source trust, confidence) use the semantic tokens.
 */
export const ANNOTATION_TYPE_META: Record<string, { label: string; badgeClass: string }> = {
  [BaseSchema.BBox]: { label: "Bounding box", badgeClass: "bg-blue-500/15 text-blue-400" },
  [BaseSchema.Mask]: { label: "Mask", badgeClass: "bg-purple-500/15 text-purple-400" },
  [BaseSchema.MultiPath]: { label: "Polyline", badgeClass: "bg-orange-500/15 text-orange-400" },
  [BaseSchema.Keypoints]: { label: "Keypoints", badgeClass: "bg-teal-500/15 text-teal-400" },
  [BaseSchema.TextSpan]: { label: "Text span", badgeClass: "bg-amber-500/15 text-amber-400" },
  [BaseSchema.Tracklet]: { label: "Track", badgeClass: "bg-cyan-500/15 text-cyan-400" },
};

export interface SourceStyle {
  class: string;
  icon: typeof User;
}

/** Badge style for an annotation source (human / model / ground truth). */
export function getSourceStyle(sourceName: string): SourceStyle {
  switch (sourceName) {
    case "Pixano":
      return { class: "bg-info/10 text-info border-info/20", icon: User };
    case "Pre-annotation":
      return { class: "bg-warning/10 text-warning border-warning/20", icon: Robot };
    case "Ground Truth":
      return { class: "bg-success/10 text-success border-success/20", icon: Target };
    default:
      return { class: "bg-muted text-muted-foreground border-border/50", icon: Robot };
  }
}

/** Badge style for a model confidence score. */
export function getConfidenceStyle(confidence: number): string {
  if (confidence >= 0.8) return "bg-success/15 text-success";
  if (confidence >= 0.5) return "bg-warning/15 text-warning";
  return "bg-destructive/15 text-destructive";
}
