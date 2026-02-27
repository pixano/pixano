/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

export interface TrackerKeyframe {
  readonly frameIndex: number;
}

export interface InterpolationResult<K extends TrackerKeyframe> {
  readonly frameIndex: number;
  readonly isKeyframe: boolean;
  readonly data: K;
}

export abstract class BaseTracker<K extends TrackerKeyframe> {
  protected keyframes: Map<number, K> = new Map();
  private _version = 0;
  readonly viewName: string;

  constructor(viewName: string) {
    this.viewName = viewName;
  }

  get version(): number {
    return this._version;
  }

  protected bump(): void {
    this._version++;
  }

  addKeyframe(keyframe: K): void {
    this.keyframes.set(keyframe.frameIndex, keyframe);
    this.bump();
  }

  removeKeyframe(frameIndex: number): boolean {
    const deleted = this.keyframes.delete(frameIndex);
    if (deleted) this.bump();
    return deleted;
  }

  isKeyframe(frameIndex: number): boolean {
    return this.keyframes.has(frameIndex);
  }

  get sortedKeyframes(): K[] {
    return Array.from(this.keyframes.values()).sort((a, b) => a.frameIndex - b.frameIndex);
  }

  get startFrame(): number | undefined {
    if (this.keyframes.size === 0) return undefined;
    let min = Infinity;
    for (const k of this.keyframes.values()) {
      if (k.frameIndex < min) min = k.frameIndex;
    }
    return min;
  }

  get endFrame(): number | undefined {
    if (this.keyframes.size === 0) return undefined;
    let max = -Infinity;
    for (const k of this.keyframes.values()) {
      if (k.frameIndex > max) max = k.frameIndex;
    }
    return max;
  }

  get keyframeCount(): number {
    return this.keyframes.size;
  }

  abstract interpolateAt(frameIndex: number): InterpolationResult<K> | null;

  promoteToKeyframe(frameIndex: number, overrideData?: Partial<K>): K | null {
    const result = this.interpolateAt(frameIndex);
    if (!result) return null;
    const promoted = overrideData ? { ...result.data, ...overrideData } : result.data;
    this.addKeyframe(promoted);
    return promoted;
  }

  clear(): void {
    this.keyframes.clear();
    this.bump();
  }
}
