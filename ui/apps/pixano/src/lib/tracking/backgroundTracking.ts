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

/** What the tracking job takes to follow one object of a video from one of its frames. */
export function trackingParams(
  model: string,
  recordId: string,
  entityId: string,
  frameIndex: number,
): Record<string, unknown> {
  return {
    model,
    objects: [{ record_id: recordId, entity_id: entityId, frame_index: frameIndex }],
  };
}

/** How far the tracking of an object got, as its card says it: in frames, while it runs. */
export function trackingSummary(job: Job): string {
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
      return doneSummary(job);
    case "cancelled":
      return "Tracking cancelled";
    default:
      return "Tracking failed";
  }
}

/** A finished job, as its card says it: a video that could not be tracked is no lost object. */
function doneSummary(job: Job): string {
  const unread = "the explorer's Jobs panel says why";
  if (job.produced === 0)
    return job.quarantined > 0
      ? `Could not track the video: ${unread}`
      : "Tracked: the object was lost on the next frame";
  const tracked = `Tracked: a mask on ${job.produced.toLocaleString()} frame${job.produced > 1 ? "s" : ""}`;
  return job.quarantined > 0 ? `${tracked}; a video could not be tracked, ${unread}` : tracked;
}
