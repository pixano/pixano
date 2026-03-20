/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { trackVideo } from "$lib/api/inferenceApi";
import type { InteractivePromptState } from "$lib/segmentation/InteractiveSegmenter";
import {
  normalizeMaskToSaveShape,
  saveMaskShapeToTrackingOutput,
} from "$lib/segmentation/maskNormalization";
import type { Reference } from "$lib/types/dataset";
import type { SaveMaskShape } from "$lib/types/shapeTypes";
import type { MaskSegmentationOutput } from "$components/inference/segmentation/inference";

import { BaseTracker, type InterpolationResult, type TrackerKeyframe } from "./BaseTracker";

export interface Sam2VideoFrameSource {
  frameIndex: number;
  viewRef: Reference;
  width: number;
  height: number;
}

export interface Sam2TrackerKeyframe extends TrackerKeyframe {
  readonly viewRef: Reference;
  readonly objectId: number;
  readonly model: string;
  readonly providerName: string;
  readonly prompt: InteractivePromptState;
  readonly mask: SaveMaskShape;
  readonly sourceKeyframeIndex?: number;
}

export class Sam2VideoTracker extends BaseTracker<Sam2TrackerKeyframe> {
  private frameSources: Sam2VideoFrameSource[] = [];
  private propagatedMasks = new Map<number, SaveMaskShape>();
  private propagatedMaskSources = new Map<number, number>();
  private readonly trackingClient: typeof trackVideo;
  private readonly datasetId: string;
  private readonly recordId: string;

  constructor(
    datasetId: string,
    recordId: string,
    viewName: string,
    trackingClientImpl: typeof trackVideo = trackVideo,
  ) {
    super(viewName);
    this.datasetId = datasetId;
    this.recordId = recordId;
    this.trackingClient = trackingClientImpl;
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
    this.bump();
  }

  override addKeyframe(keyframe: Sam2TrackerKeyframe): void {
    super.addKeyframe(keyframe);
    this.propagatedMasks.set(keyframe.frameIndex, keyframe.mask);
    this.propagatedMaskSources.set(keyframe.frameIndex, keyframe.frameIndex);
  }

  getPropagatedMask(frameIndex: number): SaveMaskShape | null {
    return this.propagatedMasks.get(frameIndex) ?? null;
  }

  getTrackingOutputs(): MaskSegmentationOutput[] {
    return Array.from(this.propagatedMasks.entries())
      .sort(([left], [right]) => left - right)
      .map(([frameIndex, mask]) => saveMaskShapeToTrackingOutput(mask, frameIndex));
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

  async propagateFromKeyframe(keyframe: Sam2TrackerKeyframe): Promise<SaveMaskShape[]> {
    if (this.frameSources.length === 0) {
      return [];
    }

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
              Math.min(
                keyframe.prompt.box.x,
                keyframe.prompt.box.x + keyframe.prompt.box.width,
              ),
            ),
            Math.round(
              Math.min(
                keyframe.prompt.box.y,
                keyframe.prompt.box.y + keyframe.prompt.box.height,
              ),
            ),
            Math.round(
              Math.max(
                keyframe.prompt.box.x,
                keyframe.prompt.box.x + keyframe.prompt.box.width,
              ),
            ),
            Math.round(
              Math.max(
                keyframe.prompt.box.y,
                keyframe.prompt.box.y + keyframe.prompt.box.height,
              ),
            ),
          ],
        ]
      : null;

    const response = await this.trackingClient({
      model: keyframe.model,
      provider_name: keyframe.providerName,
      dataset_id: this.datasetId,
      record_id: this.recordId,
      view_name: this.viewName,
      start_frame_index: this.frameSources[0]?.frameIndex ?? 0,
      frame_count: this.frameSources.length,
      objects_ids: [keyframe.objectId],
      prompt_frame_indexes: [keyframe.frameIndex],
      points,
      labels,
      boxes,
    });

    if (!response) {
      return [];
    }

    const normalizedMasks: SaveMaskShape[] = [];
    for (let index = 0; index < response.data.frame_indexes.length; index += 1) {
      const frameIndex = response.data.frame_indexes[index];
      const mask = response.data.masks[index];
      const frameSource = this.frameSources.find((frame) => frame.frameIndex === frameIndex);
      if (!mask || !frameSource) continue;

      const normalizedMask = normalizeMaskToSaveShape({
        mask,
        viewRef: frameSource.viewRef,
        itemId: keyframe.mask.itemId,
        imageWidth: frameSource.width,
        imageHeight: frameSource.height,
      });
      this.propagatedMasks.set(frameIndex, normalizedMask);
      this.propagatedMaskSources.set(frameIndex, keyframe.frameIndex);
      normalizedMasks.push(normalizedMask);
    }

    this.bump();
    return normalizedMasks;
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
}
