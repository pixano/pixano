/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type {
  PointCloudColoring,
  PointCloudColorSource,
  ProjectionCamera,
} from "./coloring/colorMode.js";
import { createColorSource } from "./coloring/colorSource.js";
import { colorModeFor } from "./coloring/registry.js";
import type { ParsedPointCloud } from "./pointCloudParser.js";

const COLOR_COMPONENTS_PER_POINT = 3;

/**
 * Owns the colours of one point cloud: which mode is active, the buffer the
 * renderer uploads, and what the mode reported about it.
 *
 * A domain class rather than logic inside the widget or the Threlte scene, for
 * the reason the coding standards give: components host and render, they do not
 * compute. It also makes the whole switch-mode path testable without mounting a
 * canvas — which matters, because the interesting behaviour here is
 * cancellation, and that is invisible from the outside.
 */
export class PointCloudColorController {
  /** The parsed cloud, once the widget's fetch has resolved. */
  cloud = $state<ParsedPointCloud | null>(null);
  /** RGB triples in [0, 1], length = pointCount × 3. */
  colors = $state<Float32Array>(new Float32Array(0));
  /** What the active mode reported: legend, uncoloured count. */
  coloring = $state<PointCloudColoring | null>(null);
  /** True while an async mode (image projection) is still computing. */
  recoloring = $state(false);
  /** Set when the active mode threw; the previous colours stay on screen. */
  error = $state<string | null>(null);

  activeModeId = $state("");

  /**
   * Bumped after every successful recolour. The buffer is written in place — its
   * identity never changes — so a consumer watching `colors` alone would never
   * re-run. This is the signal the renderer marks its attribute dirty on.
   */
  revision = $state(0);

  // `$derived.by`, not `$derived`: the record context arrives as a constructor
  // parameter property, which is assigned after class field initialisers run.
  // Reading it from inside a thunk defers that read to the first `source` access,
  // which is always after construction.
  readonly source = $derived.by<PointCloudColorSource | null>(() =>
    this.cloud
      ? createColorSource(this.cloud, {
          worldToSensor: this.worldToSensor,
          cameras: this.cameras,
        })
      : null,
  );

  /**
   * Aborts the in-flight recolour. Held so a mode switch during a slow image
   * decode cannot let the older pass finish and overwrite the newer colours —
   * the same stale-write hazard `RecordLoader` guards with its load token.
   */
  #inFlight: AbortController | null = null;

  constructor(
    private readonly cameras: readonly ProjectionCamera[],
    private readonly worldToSensor: readonly number[] | null,
  ) {}

  /** Hand over the parsed cloud and colour it with the current mode. */
  async setCloud(cloud: ParsedPointCloud): Promise<void> {
    this.cloud = cloud;
    this.colors = new Float32Array(cloud.pointCount * COLOR_COMPONENTS_PER_POINT);
    await this.#recolor();
  }

  /**
   * Switch modes. Unknown ids resolve to the default rather than failing, so a
   * persisted choice that outlived its mode degrades to the usual colours.
   */
  async setMode(modeId: string): Promise<void> {
    const resolved = colorModeFor(modeId);
    if (resolved.id === this.activeModeId && this.revision > 0) return;
    this.activeModeId = resolved.id;
    await this.#recolor();
  }

  /** Recompute with the active mode, e.g. after a mode's own controls changed. */
  async recolor(): Promise<void> {
    await this.#recolor();
  }

  dispose(): void {
    this.#inFlight?.abort();
    this.#inFlight = null;
  }

  async #recolor(): Promise<void> {
    const source = this.source;
    if (!source) return;

    this.#inFlight?.abort();
    const controller = new AbortController();
    this.#inFlight = controller;

    const mode = colorModeFor(this.activeModeId);
    // A mode that cannot run on this cloud is not an error: the widget may have
    // been restored with a mode the new record does not support. Fall back to
    // the default so the cloud is never left uncoloured.
    const usable = mode.unavailableReason?.(source) ? colorModeFor(undefined) : mode;
    this.activeModeId = usable.id;

    this.recoloring = true;
    this.error = null;
    try {
      const result = await usable.computeColors(source, this.colors, controller.signal);
      // A newer switch started while we were awaiting — its own pass owns the
      // buffer now, so drop this result rather than publishing it.
      if (controller.signal.aborted) return;
      this.coloring = result;
      this.revision++;
    } catch (e) {
      if (controller.signal.aborted) return;
      this.error = e instanceof Error ? e.message : "Failed to colour the point cloud";
    } finally {
      if (this.#inFlight === controller) {
        this.#inFlight = null;
        this.recoloring = false;
      }
    }
  }
}
