/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

/**
 * Skeleton definitions, keyed by the `template_id` a `KeyPoints` row carries.
 *
 * The backend stores only `template_id`, `coords` and `states` — it has no
 * table for templates, so **the edges and the point labels exist only here**.
 * A row whose `template_id` is unknown to this registry can still be read, but
 * it can only be drawn as loose points: there is nothing to connect them with.
 *
 * Ported from `ui/apps/pixano/src/lib/utils/keyPointsTemplates.ts`. That file
 * also carried default vertex positions; they are dropped here because points
 * are placed by clicking, so a default layout has no user.
 *
 * This is the client-side half of a gap in the data model, not a design choice
 * — see docs/OPEN_QUESTIONS.md if a backend template table is ever added.
 */

export interface KeypointTemplatePoint {
  /** Shown while placing this point, e.g. "eye left". */
  label: string;
  /** Optional per-point colour; falls back to the annotation's state colour. */
  color?: string;
}

export interface KeypointTemplate {
  id: string;
  label: string;
  points: KeypointTemplatePoint[];
  /** Index pairs into `points`, drawn as the skeleton's bones. */
  edges: readonly (readonly [number, number])[];
}

const FACE: KeypointTemplate = {
  id: "face",
  label: "Face",
  points: [
    { label: "eye left", color: "#3b82f6" },
    { label: "eye right", color: "#3b82f6" },
    { label: "nose", color: "#22c55e" },
    { label: "mouth", color: "#ef4444" },
  ],
  edges: [
    [0, 2],
    [1, 2],
    [2, 3],
  ],
};

const PERSON: KeypointTemplate = {
  id: "person",
  label: "Person",
  points: [
    { label: "head" },
    { label: "middle" },
    { label: "left arm" },
    { label: "right arm" },
    { label: "belly" },
    { label: "left foot" },
    { label: "right foot" },
  ],
  edges: [
    [0, 1],
    [1, 2],
    [1, 3],
    [1, 4],
    [4, 5],
    [4, 6],
  ],
};

const COW: KeypointTemplate = {
  id: "cow",
  label: "Cow",
  points: [
    { label: "museau" },
    { label: "dosA" },
    { label: "dosD" },
    { label: "chignon" },
    { label: "cou" },
    { label: "dosB" },
    { label: "dosC" },
    { label: "AG" },
    { label: "AD" },
    { label: "PD" },
    { label: "PG" },
  ],
  edges: [
    [0, 3],
    [3, 4],
    [4, 1],
    [1, 5],
    [5, 6],
    [6, 2],
    [1, 7],
    [1, 8],
    [2, 9],
    [2, 10],
  ],
};

/** Every known skeleton, in the order the tool cycles through them. */
export const KEYPOINT_TEMPLATES: readonly KeypointTemplate[] = [FACE, PERSON, COW];

/** The template a fresh skeleton starts from. */
export const DEFAULT_KEYPOINT_TEMPLATE = FACE;

export function keypointTemplateFor(templateId: string): KeypointTemplate | undefined {
  return KEYPOINT_TEMPLATES.find((template) => template.id === templateId);
}
