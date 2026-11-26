/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { jobsStore } from "./jobsStore.svelte";
import type { Job } from "$lib/api/jobsApi";
import {
  DEFAULT_TRACKING_OUTPUT,
  TRACKING_KIND,
  TRACKING_TASK,
  trackingModel,
  trackingParams,
  type TrackingOutput,
} from "$lib/tracking/backgroundTracking";

/**
 * The objects of the open video followed in the background, each by its tracking job.
 *
 * The jobs themselves are the jobs store's, which follows them by its event stream: this keeps
 * which job follows which object, so that the object's card shows its progress, and its end.
 */
class VideoTrackingState {
  /** The job following each object, as the server recorded it, by the object's identifier. */
  jobs = $state<Record<string, Job>>({});
  /** The objects whose job is being submitted. */
  starting = $state<string[]>([]);
  /** Why the server refused the last job submitted for an object, by the object's identifier. */
  refusals = $state<Record<string, string>>({});
  /** The frame each object's job tracks it from, by the object's identifier. */
  startFrames = $state<Record<string, number>>({});
  /** What each object's job proposes, by the object's identifier. */
  outputs = $state<Record<string, TrackingOutput>>({});
  /** What the next object followed is proposed as, chosen on a card: kept from one card to the next. */
  output = $state<TrackingOutput>(DEFAULT_TRACKING_OUTPUT);
  /** The open video's follow, until it closes: a follow closed while it asked stops there. */
  #following: symbol | null = null;

  /**
   * Follow the jobs from the open video: their progress reaches the cards as it happens.
   *
   * Asks first, quietly, whether a worker runs tracking: an installation without a queue is no
   * error to log on every video opened, and has nothing to follow.
   */
  async follow(): Promise<void> {
    const following = Symbol("open video");
    this.#following = following;
    await jobsStore.probe();
    if (this.#following !== following || !this.available) return;
    await jobsStore.start();
  }

  unfollow(): void {
    this.#following = null;
    jobsStore.stop();
  }

  /** Whether a worker can follow an object here: one declared the tracking kind. */
  get available(): boolean {
    return jobsStore.offers(TRACKING_KIND);
  }

  /**
   * Whether the workers' tracking job lets one choose what it proposes: one older than the choice
   * proposes masks, and refuses being asked.
   */
  get offersOutputs(): boolean {
    const kind = jobsStore.kinds.find((declared) => declared.name === TRACKING_KIND);
    return kind?.params_schema.properties?.output !== undefined;
  }

  /** The model a tracking job would run, given the one chosen for the video tools. */
  modelFor(selected: string | undefined): string | null {
    return trackingModel(selected, jobsStore.servedModels[TRACKING_TASK]);
  }

  /**
   * The job following an object, as the jobs store last heard of it; as it was recorded, until the
   * store's list holds it — a list asked for before the job was submitted can land after it.
   */
  jobOf(entityId: string): Job | null {
    const launched = this.jobs[entityId];
    if (!launched) return null;
    return jobsStore.jobs.find((job) => job.id === launched.id) ?? launched;
  }

  /** Why the server refused the last job submitted for an object, in its words; null when it did not. */
  refusalOf(entityId: string): string | null {
    return this.refusals[entityId] ?? null;
  }

  /** What an object's job proposes; masks, what a job proposes by default, when none of this page follows it. */
  outputOf(entityId: string): TrackingOutput {
    return this.outputs[entityId] ?? DEFAULT_TRACKING_OUTPUT;
  }

  /**
   * The frame after the one an object's job tracks it from, where the object was drawn: the first its
   * masks or boxes can be on. Null when no job of this page follows the object.
   */
  firstTrackedFrame(entityId: string): number | null {
    const start = this.startFrames[entityId];
    return start === undefined ? null : start + 1;
  }

  /**
   * Follow an object of a video from a frame where it is annotated, to the video's end.
   *
   * @param output What the job proposes; none asked, where the workers' job offers no choice, is masks.
   * @returns Whether the job was accepted.
   */
  async track(
    datasetId: string,
    recordId: string,
    entityId: string,
    frameIndex: number,
    model: string,
    output?: TrackingOutput,
  ): Promise<boolean> {
    if (this.starting.includes(entityId)) return false;
    this.starting = [...this.starting, entityId];
    this.refusals = withoutKey(this.refusals, entityId);
    try {
      const job = await jobsStore.launch(
        TRACKING_KIND,
        datasetId,
        trackingParams(model, recordId, entityId, frameIndex, output),
      );
      if (job === null) {
        this.refusals = {
          ...this.refusals,
          [entityId]: jobsStore.error ?? jobsStore.unavailable ?? REFUSED,
        };
        return false;
      }
      this.jobs = { ...this.jobs, [entityId]: job };
      this.startFrames = { ...this.startFrames, [entityId]: frameIndex };
      this.outputs = { ...this.outputs, [entityId]: output ?? DEFAULT_TRACKING_OUTPUT };
      return true;
    } finally {
      this.starting = this.starting.filter((starting) => starting !== entityId);
    }
  }

  /** Stop following an object: its job stops between two windows of frames, and writes nothing. */
  async cancel(entityId: string): Promise<void> {
    const launched = this.jobs[entityId];
    if (launched) await jobsStore.cancel(launched.id);
  }

  /** Forget an object's job, once its card has shown its end. */
  dismiss(entityId: string): void {
    this.jobs = withoutKey(this.jobs, entityId);
    this.startFrames = withoutKey(this.startFrames, entityId);
    this.outputs = withoutKey(this.outputs, entityId);
  }
}

/** What a card says when the server refused a job without a reason the store could read. */
const REFUSED = "The server refused to track this object.";

function withoutKey<T>(record: Record<string, T>, key: string): Record<string, T> {
  const remaining = { ...record };
  delete remaining[key];
  return remaining;
}

export const videoTracking = new VideoTrackingState();
