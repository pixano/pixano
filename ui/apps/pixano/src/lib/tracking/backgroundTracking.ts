/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { Job } from "$lib/api/jobsApi";
import { BaseSchema, type Annotation, type Entity } from "$lib/types/dataset";

/** The job kind that follows an object through its video, in the background (pixano-worker's `tracking`). */
export const TRACKING_KIND = "tracking";
/** The task of the models it runs, as the inference lists them. */
export const TRACKING_TASK = "video_mask_generation";

/**
 * What a tracking job proposes on each frame it follows an object to (pixano-worker's `output`): the
 * object's mask, the box around that mask, or both.
 */
export type TrackingOutput = "masks" | "boxes" | "both";
/** What the job proposes unless asked otherwise. */
export const DEFAULT_TRACKING_OUTPUT: TrackingOutput = "masks";
/** The choices, as an object's card offers them. */
export const TRACKING_OUTPUTS: readonly { value: TrackingOutput; label: string }[] = [
  { value: "masks", label: "Masks" },
  { value: "boxes", label: "Boxes" },
  { value: "both", label: "Masks and boxes" },
];

/** A choice read back from the card's list; what the job proposes by default for anything else. */
export function trackingOutput(value: string): TrackingOutput {
  return (
    TRACKING_OUTPUTS.find((choice) => choice.value === value)?.value ?? DEFAULT_TRACKING_OUTPUT
  );
}

/** What a tracking job proposes, as the card's sentences name it. */
function proposed(output: TrackingOutput): string {
  return output === "both" ? "masks and boxes" : output;
}

/** What the card says a job would do, before it is launched. */
export function trackingHint(model: string | null, output: TrackingOutput): string {
  const proposals = output === "both" ? "masks and their boxes" : output;
  return `From this frame to the video's end, with ${model}. The ${proposals} arrive pending review.`;
}

/** The button that shows what a finished job wrote. */
export function showTrackedLabel(output: TrackingOutput): string {
  return `Show the ${proposed(output)}`;
}

/** The frame an annotation is drawn on, in a video; none for one that is not on a frame. */
function frameOf(annotation: Annotation): number | undefined {
  return annotation.ui.frame_index ?? (annotation.data as { frame_index?: number }).frame_index;
}

/** Whether an object can be followed from a frame: it holds a box or a mask there, to start from. */
export function canTrackFrom(entity: Entity, frameIndex: number): boolean {
  return (entity.ui.childs ?? []).some(
    (child) =>
      (child.is_type(BaseSchema.BBox) || child.is_type(BaseSchema.Mask)) &&
      frameOf(child) === frameIndex,
  );
}

/**
 * The tracking model to run: the one chosen for the video tools when the inference serves it for
 * tracking, else the first it serves; the one chosen when the inference could not say.
 */
export function trackingModel(
  selected: string | undefined,
  served: string[] | undefined,
): string | null {
  if (served && served.length > 0)
    return selected && served.includes(selected) ? selected : served[0];
  return selected || null;
}

/** Why an object cannot be followed from the frame shown, as its card says it; null when it can. */
export function trackingBlocker(state: {
  /** A worker declared the tracking kind. */
  available: boolean;
  /** The model a job would run; null when the inference serves none for tracking. */
  model: string | null;
  /** The workspace holds changes not saved yet: the job reads the saved video. */
  unsaved: boolean;
  /** The frame shown is the video's last. */
  lastFrame: boolean;
}): string | null {
  if (!state.available)
    return "No worker runs tracking here: start pixano-worker to follow objects in the background.";
  if (state.model === null) return "The inference serves no tracking model.";
  if (state.unsaved) return "Save your changes first: the job follows the object as it is saved.";
  if (state.lastFrame)
    return "This is the video's last frame: there is nothing after it to follow.";
  return null;
}

/**
 * Why "Show the masks" — or the boxes — cannot read the record again now, as the card says it; null
 * when it can. Reading it again drops what is not saved, and leaves the objects the Fusion tool picked
 * pointing at objects no longer shown; leaving the drawing tool, for what the job wrote to show, ends
 * a box or mask tracking session.
 */
export function showTrackedBlocker(state: {
  /** The workspace holds changes not saved yet. */
  unsaved: boolean;
  /** Why the edit mode is blocked — a tracking session, Fusion —; or null. */
  session: string | null;
}): string | null {
  if (state.unsaved) return "Save your changes first, then show them.";
  if (state.session !== null) return `${state.session}.`;
  return null;
}

/**
 * What the tracking job takes to follow one object of a video from one of its frames. Without an
 * output, none is sent: a worker older than the choice refuses a parameter it does not know, and
 * proposes masks.
 */
export function trackingParams(
  model: string,
  recordId: string,
  entityId: string,
  frameIndex: number,
  output?: TrackingOutput,
): Record<string, unknown> {
  return {
    model,
    objects: [{ record_id: recordId, entity_id: entityId, frame_index: frameIndex }],
    ...(output === undefined ? {} : { output }),
  };
}

/** How far the tracking of an object got, as its card says it: in frames, while it runs. */
export function trackingSummary(
  job: Job,
  output: TrackingOutput = DEFAULT_TRACKING_OUTPUT,
): string {
  switch (job.state) {
    case "planning":
    case "pending":
      return job.cancel_requested ? "Cancelling…" : "Waiting for a worker…";
    case "running":
      if (job.cancel_requested) return "Cancelling…";
      return job.finalizing
        ? "Finishing…"
        : `Tracking: ${job.done_tasks.toLocaleString()} / ${job.total_tasks.toLocaleString()} frames`;
    case "done":
      return doneSummary(job, output);
    case "cancelled":
      return "Tracking cancelled";
    default:
      return "Tracking failed";
  }
}

/** What a finished job proposed on each frame it produced, as its card says it. */
const PROPOSED_ON_A_FRAME: Record<TrackingOutput, string> = {
  masks: "a mask",
  boxes: "a box",
  both: "a mask and its box",
};

/** A finished job, as its card says it: a video that could not be tracked is no lost object. */
function doneSummary(job: Job, output: TrackingOutput): string {
  const unread = "the explorer's Jobs panel says why";
  if (job.produced === 0)
    return job.quarantined > 0
      ? `Could not track the video: ${unread}`
      : "Tracked: the object was lost on the next frame";
  const frames = `${job.produced.toLocaleString()} frame${job.produced > 1 ? "s" : ""}`;
  const tracked = `Tracked: ${PROPOSED_ON_A_FRAME[output]} on ${frames}`;
  return job.quarantined > 0 ? `${tracked}; a video could not be tracked, ${unread}` : tracked;
}
