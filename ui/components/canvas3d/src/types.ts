/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { Document, NodeId } from "@pixano/document";
import type { ToolEvent } from "@pixano/tools";

// --------------- 3D Renderer Adapter ---------------

/**
 * Renderer adapter interface for the 3D canvas.
 * Same contract as the 2D adapter for multi-view coordination.
 */
export interface Canvas3DRendererAdapter {
  mount(container: HTMLElement): void;
  unmount(): void;
  setDocument(document: Document): void;
  setSelection(selectedIds: ReadonlySet<NodeId>): void;
  onToolEvent(event: ToolEvent): void;
  getViewName(): string;
}

// --------------- Point Cloud ---------------

export interface PointCloudData {
  readonly positions: Float32Array; // xyz interleaved
  readonly colors?: Uint8Array; // rgb interleaved
  readonly intensities?: Float32Array;
  readonly pointCount: number;
}

// --------------- 3D Bounding Box ---------------

export interface BBox3D {
  readonly center: { x: number; y: number; z: number };
  readonly dimensions: { width: number; height: number; depth: number };
  readonly rotation?: { x: number; y: number; z: number }; // Euler angles in radians
  readonly label?: string;
  readonly color?: string;
}

// --------------- Camera ---------------

export interface CameraState {
  readonly position: { x: number; y: number; z: number };
  readonly target: { x: number; y: number; z: number };
  readonly up: { x: number; y: number; z: number };
  readonly fov: number;
}
