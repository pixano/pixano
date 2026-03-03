/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { LinearBBTracker, type BBoxKeyframe } from "./LinearBBTracker";
import type { InterpolationResult } from "./BaseTracker";

export interface SegmentInfo {
  readonly index: number;
  readonly startFrame: number | undefined;
  readonly endFrame: number | undefined;
  readonly keyframeCount: number;
}

export class MultiSegmentTracker {
  private segments: LinearBBTracker[] = [];
  private _version = 0;
  readonly viewName: string;

  constructor(viewName: string) {
    this.viewName = viewName;
    this.segments.push(new LinearBBTracker(viewName));
  }

  get version(): number {
    return this._version;
  }

  private bump(): void {
    this._version++;
  }

  // ─── Segment access ──────────────────────────────────────────────────────

  get segmentCount(): number {
    return this.segments.length;
  }

  get activeSegmentIndex(): number {
    return this.segments.length - 1;
  }

  get activeSegment(): LinearBBTracker {
    return this.segments[this.segments.length - 1];
  }

  /** Start a new empty segment. No-op if the active segment is already empty. */
  startNewSegment(): boolean {
    if (this.activeSegment.keyframeCount === 0) return false;
    this.segments.push(new LinearBBTracker(this.viewName));
    this.bump();
    return true;
  }

  /** Find which segment index owns a given frame, or -1 if in a gap. */
  findSegmentAt(frameIndex: number): number {
    for (let i = 0; i < this.segments.length; i++) {
      const seg = this.segments[i];
      const start = seg.startFrame;
      const end = seg.endFrame;
      if (start !== undefined && end !== undefined && frameIndex >= start && frameIndex <= end) {
        return i;
      }
    }
    return -1;
  }

  // ─── Keyframe operations ─────────────────────────────────────────────────

  /** Add a keyframe, routing to the segment that owns the frame range. */
  addKeyframe(kf: BBoxKeyframe): boolean {
    // Route to the finalized segment that owns this frame range
    for (let i = 0; i < this.segments.length - 1; i++) {
      const seg = this.segments[i];
      const start = seg.startFrame;
      const end = seg.endFrame;
      if (start !== undefined && end !== undefined && kf.frameIndex >= start && kf.frameIndex <= end) {
        seg.addKeyframe(kf);
        this.bump();
        return true;
      }
    }
    // Not in any finalized segment → add to active segment
    this.activeSegment.addKeyframe(kf);
    this.bump();
    return true;
  }

  /** Interpolate across all segments. Returns null for frames in gaps. */
  interpolateAt(frameIndex: number): InterpolationResult<BBoxKeyframe> | null {
    for (const seg of this.segments) {
      const result = seg.interpolateAt(frameIndex);
      if (result) return result;
    }
    return null;
  }

  /** Check if a frame is a keyframe in any segment. */
  isKeyframe(frameIndex: number): boolean {
    return this.segments.some((seg) => seg.isKeyframe(frameIndex));
  }

  /** Promote a frame to keyframe in the segment that owns it. */
  promoteToKeyframe(
    frameIndex: number,
    overrideData?: Partial<BBoxKeyframe>,
  ): BBoxKeyframe | null {
    const segIdx = this.findSegmentAt(frameIndex);
    const target = segIdx >= 0 ? this.segments[segIdx] : this.activeSegment;
    const result = target.promoteToKeyframe(frameIndex, overrideData);
    if (result) this.bump();
    return result;
  }

  // ─── Aggregate getters (backward compat) ─────────────────────────────────

  /** All keyframes across all segments, sorted by frame index. */
  get sortedKeyframes(): BBoxKeyframe[] {
    const all: BBoxKeyframe[] = [];
    for (const seg of this.segments) {
      all.push(...seg.sortedKeyframes);
    }
    return all.sort((a, b) => a.frameIndex - b.frameIndex);
  }

  /** Total keyframe count across all segments. */
  get keyframeCount(): number {
    let count = 0;
    for (const seg of this.segments) count += seg.keyframeCount;
    return count;
  }

  /** Earliest frame across all segments. */
  get startFrame(): number | undefined {
    let min: number | undefined;
    for (const seg of this.segments) {
      const s = seg.startFrame;
      if (s !== undefined && (min === undefined || s < min)) min = s;
    }
    return min;
  }

  /** Latest frame across all segments. */
  get endFrame(): number | undefined {
    let max: number | undefined;
    for (const seg of this.segments) {
      const e = seg.endFrame;
      if (e !== undefined && (max === undefined || e > max)) max = e;
    }
    return max;
  }

  // ─── Per-segment data (for save logic & timeline) ────────────────────────

  /** Per-segment keyframe arrays, filtering out empty segments. */
  get segmentKeyframes(): BBoxKeyframe[][] {
    return this.segments
      .filter((seg) => seg.keyframeCount > 0)
      .map((seg) => seg.sortedKeyframes);
  }

  /** Per-segment frame ranges [start, end], filtering out empty segments. */
  get segmentRanges(): Array<[number, number]> {
    const ranges: Array<[number, number]> = [];
    for (const seg of this.segments) {
      const start = seg.startFrame;
      const end = seg.endFrame;
      if (start !== undefined && end !== undefined) {
        ranges.push([start, end]);
      }
    }
    return ranges;
  }

  /** Per-segment info for UI display. */
  get segmentInfos(): SegmentInfo[] {
    return this.segments.map((seg, i) => ({
      index: i,
      startFrame: seg.startFrame,
      endFrame: seg.endFrame,
      keyframeCount: seg.keyframeCount,
    }));
  }

  // ─── Lifecycle ───────────────────────────────────────────────────────────

  clear(): void {
    this.segments = [new LinearBBTracker(this.viewName)];
    this.bump();
  }
}
