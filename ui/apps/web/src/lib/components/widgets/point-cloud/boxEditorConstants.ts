/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import * as THREE from "three";

// ─── Sizing fractions (relative to gizmo ring radius) ────────────────────────

export const GIZMO_RING_PADDING = 1.2;
export const GIZMO_TUBE_FRACTION = 0.0225;
export const GIZMO_ARROW_HEIGHT_FRACTION = 0.50;
export const GIZMO_ARROW_RADIUS_FRACTION = 0.09;
export const GIZMO_ARROW_GAP_FRACTION = 0.04;
export const GIZMO_ARROW_HEAD_FRACTION = 0.42;
export const GIZMO_ARROW_SHAFT_RADIUS_FRACTION = 0.30;
export const MIN_GEOMETRY_SIZE = 0.01;
export const DEFAULT_BOX_SIZE_FRACTION = 0.12;

// ─── Gizmo definitions ────────────────────────────────────────────────────────

/** Three torus rings, one per world axis (X/Y/Z). */
export const RING_DEFS = [
  { color: "#ef4444", euler: new THREE.Euler(0, Math.PI / 2, 0) },
  { color: "#22c55e", euler: new THREE.Euler(Math.PI / 2, 0, 0) },
  { color: "#3b82f6", euler: new THREE.Euler(0, 0, 0) },
] as const;

/**
 * Pre-baked local quaternions from RING_DEFS.
 * Avoids recomputing in each BoxEditor constructor.
 */
export const RING_LOCAL_QUATS = RING_DEFS.map((r) =>
  new THREE.Quaternion().setFromEuler(r.euler),
);

/** Component pair [a, b] used in atan2(d[a], d[b]) for each ring axis. */
export const RING_ATAN_AXES = [[2, 1], [2, 0], [1, 0]] as const;

/** Six resize arrows — one for each ±axis face. */
export const ARROW_DEFS = [
  { id: "+x", localDir: new THREE.Vector3( 1,  0,  0), color: "#ef4444", axis: 0 as const, sign:  1 as const },
  { id: "-x", localDir: new THREE.Vector3(-1,  0,  0), color: "#ef4444", axis: 0 as const, sign: -1 as const },
  { id: "+y", localDir: new THREE.Vector3( 0,  1,  0), color: "#3b82f6", axis: 1 as const, sign:  1 as const },
  { id: "-y", localDir: new THREE.Vector3( 0, -1,  0), color: "#3b82f6", axis: 1 as const, sign: -1 as const },
  { id: "+z", localDir: new THREE.Vector3( 0,  0,  1), color: "#22c55e", axis: 2 as const, sign:  1 as const },
  { id: "-z", localDir: new THREE.Vector3( 0,  0, -1), color: "#22c55e", axis: 2 as const, sign: -1 as const },
] as const;

/** Three translate arrows — one per +axis direction from box center. */
export const TRANSLATE_ARROW_DEFS = [
  { id: "+x", localDir: new THREE.Vector3(1, 0, 0), color: "#ef4444", axis: 0 as const },
  { id: "+y", localDir: new THREE.Vector3(0, 1, 0), color: "#3b82f6", axis: 1 as const },
  { id: "+z", localDir: new THREE.Vector3(0, 0, 1), color: "#22c55e", axis: 2 as const },
] as const;

/** Unit vectors for each axis — used for ring-angle raycasting. */
export const AXIS_UNIT_VECS = [
  new THREE.Vector3(1, 0, 0),
  new THREE.Vector3(0, 1, 0),
  new THREE.Vector3(0, 0, 1),
] as const;

/** Canonical "up" axis for arrow orientation. */
export const ARROW_UP = new THREE.Vector3(0, 1, 0);
