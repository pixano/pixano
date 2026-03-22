/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { MaskSegmentationOutput } from "$components/inference/segmentation/inference";

import { BaseTracker, type InterpolationResult, type TrackerKeyframe } from "./BaseTracker";
import {
  cancelTrackingJob,
  getTrackingJob,
  submitTrackingJob,
  trackVideo,
} from "$lib/api/inferenceApi";
import type { InteractivePromptState } from "$lib/segmentation/InteractiveSegmenter";
import {
  normalizeMaskToSaveShape,
  saveMaskShapeToTrackingOutput,
  type TrackingMaskSourceInput,
} from "$lib/segmentation/maskNormalization";
import type { Reference } from "$lib/types/dataset";
import type {
  VideoTrackingJobStatus,
  VideoTrackingTaskInput,
  VideoTrackingTaskOutput,
} from "$lib/types/inference";
import type { SaveMaskShape } from "$lib/types/shapeTypes";

export interface Sam2VideoFrameSource {
  frameIndex: number;
  viewRef: Reference;
  width: number;
  height: number;
}

export interface Sam2TrackerPromptKeyframe extends TrackerKeyframe {
  readonly viewRef: Reference;
  readonly objectId: number;
  readonly model: string;
  readonly providerName: string;
  readonly itemId: string;
  readonly prompt: InteractivePromptState & { mask?: SaveMaskShape | null };
}

export interface Sam2TrackerKeyframe extends Sam2TrackerPromptKeyframe {
  readonly mask: SaveMaskShape;
  readonly sourceKeyframeIndex?: number;
}

export interface Sam2VideoTrackerJobClients {
  submitTrackingJobClient: typeof submitTrackingJob;
  getTrackingJobClient: typeof getTrackingJob;
  cancelTrackingJobClient: typeof cancelTrackingJob;
}

export class Sam2VideoTracker extends BaseTracker<Sam2TrackerKeyframe> {
  private frameSources: Sam2VideoFrameSource[] = [];
  private propagatedMasks = new Map<number, SaveMaskShape>();
  private propagatedMaskSources = new Map<number, number>();
  private propagatedMaskProvenance = new Map<number, TrackingMaskSourceInput>();
  private readonly trackingClient: typeof trackVideo;
  private readonly submitTrackingJobClient: typeof submitTrackingJob;
  private readonly getTrackingJobClient: typeof getTrackingJob;
  private readonly cancelTrackingJobClient: typeof cancelTrackingJob;
  private readonly datasetId: string;
  private readonly recordId: string;

  constructor(
    datasetId: string,
    recordId: string,
    viewName: string,
    trackingClientImpl: typeof trackVideo = trackVideo,
    trackingJobClients: Partial<Sam2VideoTrackerJobClients> = {},
  ) {
    super(viewName);
    this.datasetId = datasetId;
    this.recordId = recordId;
    this.trackingClient = trackingClientImpl;
    this.submitTrackingJobClient = trackingJobClients.submitTrackingJobClient ?? submitTrackingJob;
    this.getTrackingJobClient = trackingJobClients.getTrackingJobClient ?? getTrackingJob;
    this.cancelTrackingJobClient = trackingJobClients.cancelTrackingJobClient ?? cancelTrackingJob;
  }

  setFrameSources(frameSources: Sam2VideoFrameSource[]): void {
    this.frameSources = [...frameSources].sort((a, b) => a.frameIndex - b.frameIndex);
    this.bump();
  }

  override clear(): void {
    super.clear();
    this.frameSources = [];
    this.propagatedMasks.clear();
    this.propagatedMaskSources.clear();
    this.propagatedMaskProvenance.clear();
    this.bump();
  }

  override addKeyframe(keyframe: Sam2TrackerKeyframe): void {
    super.addKeyframe(keyframe);
    this.propagatedMasks.set(keyframe.frameIndex, keyframe.mask);
    this.propagatedMaskSources.set(keyframe.frameIndex, keyframe.frameIndex);
    this.propagatedMaskProvenance.set(keyframe.frameIndex, this.toTrackingMaskSource(keyframe));
  }

  async predictKeyframe(keyframe: Sam2TrackerPromptKeyframe): Promise<SaveMaskShape | null> {
    const requestFrameSource = this.frameSources.find(
      (frame) => frame.frameIndex === keyframe.frameIndex,
    );
    if (!requestFrameSource) {
      return null;
    }

    const normalizedMasks = await this.runTrackingRequest([requestFrameSource], keyframe, {
      propagate: false,
    });
    return normalizedMasks[0] ?? null;
  }

  async submitPredictKeyframeJob(
    keyframe: Sam2TrackerPromptKeyframe,
  ): Promise<VideoTrackingJobStatus | null> {
    const requestFrameSource = this.frameSources.find(
      (frame) => frame.frameIndex === keyframe.frameIndex,
    );
    if (!requestFrameSource) {
      return null;
    }

    return this.submitTrackingJobClient(
      this.buildTrackingRequest([requestFrameSource], keyframe, {
        propagate: false,
      }),
    );
  }

  getPropagatedMask(frameIndex: number): SaveMaskShape | null {
    return this.propagatedMasks.get(frameIndex) ?? null;
  }

  getTrackingOutputs(): MaskSegmentationOutput[] {
    return Array.from(this.propagatedMasks.entries())
      .sort(([left], [right]) => left - right)
      .map(([frameIndex, mask]) =>
        saveMaskShapeToTrackingOutput(mask, frameIndex, this.resolveTrackingMaskSource(frameIndex)),
      );
  }

  getTrackingOutputsInRange(startFrame: number, endFrame: number): MaskSegmentationOutput[] {
    const minFrame = Math.min(startFrame, endFrame);
    const maxFrame = Math.max(startFrame, endFrame);
    return Array.from(this.propagatedMasks.entries())
      .filter(([frameIndex]) => frameIndex >= minFrame && frameIndex <= maxFrame)
      .sort(([left], [right]) => left - right)
      .map(([frameIndex, mask]) =>
        saveMaskShapeToTrackingOutput(mask, frameIndex, this.resolveTrackingMaskSource(frameIndex)),
      );
  }

  override interpolateAt(frameIndex: number): InterpolationResult<Sam2TrackerKeyframe> | null {
    const keyframe = this.keyframes.get(frameIndex);
    if (keyframe) {
      return {
        frameIndex,
        isKeyframe: true,
        data: keyframe,
      };
    }

    const propagatedMask = this.propagatedMasks.get(frameIndex);
    if (!propagatedMask) {
      return null;
    }

    const sourceKeyframeIndex = this.propagatedMaskSources.get(frameIndex);
    const nearestKeyframe =
      sourceKeyframeIndex !== undefined
        ? this.keyframes.get(sourceKeyframeIndex)
        : this.findNearestKeyframe(frameIndex);
    if (!nearestKeyframe) {
      return null;
    }

    return {
      frameIndex,
      isKeyframe: false,
      data: {
        ...nearestKeyframe,
        frameIndex,
        viewRef: propagatedMask.viewRef,
        mask: propagatedMask,
        sourceKeyframeIndex:
          sourceKeyframeIndex !== undefined ? sourceKeyframeIndex : nearestKeyframe.frameIndex,
      },
    };
  }

  async propagateInterval(
    startFrame: number,
    endFrame: number,
    keyframe: Sam2TrackerKeyframe,
  ): Promise<SaveMaskShape[]> {
    const minFrame = Math.min(startFrame, endFrame);
    const maxFrame = Math.max(startFrame, endFrame);
    const intervalSources = this.frameSources.filter(
      (f) => f.frameIndex >= minFrame && f.frameIndex <= maxFrame,
    );

    if (intervalSources.length === 0) {
      return [];
    }

    return this.runTrackingRequest(intervalSources, keyframe, {
      propagate: true,
      interval: {
        start_frame: startFrame,
        end_frame: endFrame,
        direction: endFrame >= startFrame ? "forward" : "backward",
      },
    });
  }

  async submitPropagateIntervalJob(
    startFrame: number,
    endFrame: number,
    keyframe: Sam2TrackerKeyframe,
  ): Promise<VideoTrackingJobStatus | null> {
    const minFrame = Math.min(startFrame, endFrame);
    const maxFrame = Math.max(startFrame, endFrame);
    const intervalSources = this.frameSources.filter(
      (frame) => frame.frameIndex >= minFrame && frame.frameIndex <= maxFrame,
    );

    if (intervalSources.length === 0) {
      return null;
    }

    return this.submitTrackingJobClient(
      this.buildTrackingRequest(intervalSources, keyframe, {
        propagate: true,
        interval: {
          start_frame: startFrame,
          end_frame: endFrame,
          direction: endFrame >= startFrame ? "forward" : "backward",
        },
      }),
    );
  }

  async propagateFromKeyframe(keyframe: Sam2TrackerKeyframe): Promise<SaveMaskShape[]> {
    if (this.frameSources.length === 0) {
      return [];
    }

    return this.runTrackingRequest(this.frameSources, keyframe, { propagate: true });
  }

  async getTrackingJobStatus(jobId: string): Promise<VideoTrackingJobStatus> {
    return this.getTrackingJobClient(jobId);
  }

  async cancelTrackingJob(jobId: string): Promise<VideoTrackingJobStatus> {
    return this.cancelTrackingJobClient(jobId);
  }

  applyTrackingResult(
    trackingOutput: VideoTrackingTaskOutput | null | undefined,
    keyframe: Sam2TrackerPromptKeyframe,
  ): SaveMaskShape[] {
    if (!trackingOutput) {
      return [];
    }

    const normalizedMasks: SaveMaskShape[] = [];
    for (let index = 0; index < trackingOutput.frame_indexes.length; index += 1) {
      const frameIndex = trackingOutput.frame_indexes[index];
      const mask = trackingOutput.masks[index];
      const frameSource = this.frameSources.find((frame) => frame.frameIndex === frameIndex);
      if (!mask || !frameSource) continue;

      const normalizedMask = normalizeMaskToSaveShape({
        mask,
        viewRef: frameSource.viewRef,
        itemId: keyframe.itemId,
        imageWidth: frameSource.width,
        imageHeight: frameSource.height,
      });
      this.propagatedMasks.set(frameIndex, normalizedMask);
      this.propagatedMaskSources.set(frameIndex, keyframe.frameIndex);
      this.propagatedMaskProvenance.set(frameIndex, this.toTrackingMaskSource(keyframe));
      normalizedMasks.push(normalizedMask);
    }

    this.bump();
    return normalizedMasks;
  }

  private buildTrackingRequest(
    requestFrameSources: Sam2VideoFrameSource[],
    keyframe: Sam2TrackerPromptKeyframe,
    options: {
      propagate: boolean;
      interval?: {
        start_frame: number;
        end_frame: number;
        direction: "forward" | "backward";
      };
    },
  ): VideoTrackingTaskInput {
    const points = keyframe.prompt.points.length
      ? [keyframe.prompt.points.map((point) => [Math.round(point.x), Math.round(point.y)])]
      : null;
    const labels = keyframe.prompt.points.length
      ? [keyframe.prompt.points.map((point) => point.label)]
      : null;
    const boxes = keyframe.prompt.box
      ? [
          [
            Math.round(
              Math.min(keyframe.prompt.box.x, keyframe.prompt.box.x + keyframe.prompt.box.width),
            ),
            Math.round(
              Math.min(keyframe.prompt.box.y, keyframe.prompt.box.y + keyframe.prompt.box.height),
            ),
            Math.round(
              Math.max(keyframe.prompt.box.x, keyframe.prompt.box.x + keyframe.prompt.box.width),
            ),
            Math.round(
              Math.max(keyframe.prompt.box.y, keyframe.prompt.box.y + keyframe.prompt.box.height),
            ),
          ],
        ]
      : null;

    return {
      model: keyframe.model,
      provider_name: keyframe.providerName,
      dataset_id: this.datasetId,
      record_id: this.recordId,
      view_name: this.viewName,
      start_frame_index: requestFrameSources[0]?.frameIndex ?? keyframe.frameIndex,
      frame_count: requestFrameSources.length,
      objects_ids: [keyframe.objectId],
      prompt_frame_indexes: [keyframe.frameIndex],
      points,
      labels,
      boxes,
      propagate: options.propagate,
      interval: options.interval ?? null,
      keyframes: [
        {
          frame_index: keyframe.frameIndex,
          points: keyframe.prompt.points.map((point) => ({
            x: Math.round(point.x),
            y: Math.round(point.y),
            label: point.label,
          })),
          box: keyframe.prompt.box
            ? {
                x: Math.round(keyframe.prompt.box.x),
                y: Math.round(keyframe.prompt.box.y),
                width: Math.round(keyframe.prompt.box.width),
                height: Math.round(keyframe.prompt.box.height),
              }
            : null,
          mask: keyframe.prompt.mask?.rle
            ? {
                counts: keyframe.prompt.mask.rle.counts,
                size: keyframe.prompt.mask.rle.size,
              }
            : null,
        },
      ],
    };
  }

  private async runTrackingRequest(
    requestFrameSources: Sam2VideoFrameSource[],
    keyframe: Sam2TrackerPromptKeyframe,
    options: {
      propagate: boolean;
      interval?: {
        start_frame: number;
        end_frame: number;
        direction: "forward" | "backward";
      };
    },
  ): Promise<SaveMaskShape[]> {
    const response = await this.trackingClient(
      this.buildTrackingRequest(requestFrameSources, keyframe, options),
    );
    return this.applyTrackingResult(response.data, keyframe);
  }

  private findNearestKeyframe(frameIndex: number): Sam2TrackerKeyframe | null {
    const keyframes = this.sortedKeyframes;
    if (keyframes.length === 0) {
      return null;
    }

    let nearest: Sam2TrackerKeyframe | null = null;
    let nearestDistance = Number.POSITIVE_INFINITY;
    for (const candidate of keyframes) {
      const distance = Math.abs(candidate.frameIndex - frameIndex);
      if (distance < nearestDistance) {
        nearest = candidate;
        nearestDistance = distance;
        continue;
      }

      if (distance === nearestDistance && nearest && candidate.frameIndex < nearest.frameIndex) {
        nearest = candidate;
      }
    }

    return nearest;
  }

  private toTrackingMaskSource(keyframe: Sam2TrackerPromptKeyframe): TrackingMaskSourceInput {
    return {
      modelName: keyframe.model,
      providerName: keyframe.providerName,
    };
  }

  private resolveTrackingMaskSource(frameIndex: number): TrackingMaskSourceInput {
    return this.propagatedMaskProvenance.get(frameIndex) ?? {};
  }
}
