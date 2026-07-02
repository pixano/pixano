/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { describe, expect, it } from "vitest";

import * as THREE from "three";

import {
  bboxTransform,
  lanceRotationToThree,
  lanceToThree,
  threeBoxToLanceXYZWHD,
  threeQuaternionToLanceRotation,
} from "../coordinateTransforms";
import type { LocalBBox3D } from "$lib/api/annotations";

// ─── lanceToThree ─────────────────────────────────────────────────────────────

describe("lanceToThree", () => {
  it("maps x unchanged, z to Three.js y, and negates y to Three.js z", () => {
    expect(lanceToThree(1, 2, 3)).toEqual([1, 3, -2]);
  });

  it("maps origin to origin", () => {
    const [x, y, z] = lanceToThree(0, 0, 0);
    expect(x).toBeCloseTo(0);
    expect(y).toBeCloseTo(0);
    expect(z).toBeCloseTo(0);
  });

  it("handles negative coordinates", () => {
    expect(lanceToThree(-1, -2, -3)).toEqual([-1, -3, 2]);
  });
});

// ─── lanceRotationToThree ─────────────────────────────────────────────────────

describe("lanceRotationToThree", () => {
  it("returns identity quaternion for undefined rotation", () => {
    const q = lanceRotationToThree(undefined);
    expect(q.x).toBeCloseTo(0);
    expect(q.y).toBeCloseTo(0);
    expect(q.z).toBeCloseTo(0);
    expect(q.w).toBeCloseTo(1);
  });

  it("returns identity quaternion for the identity matrix", () => {
    const q = lanceRotationToThree([1, 0, 0, 0, 1, 0, 0, 0, 1]);
    expect(q.x).toBeCloseTo(0);
    expect(q.y).toBeCloseTo(0);
    expect(q.z).toBeCloseTo(0);
    expect(q.w).toBeCloseTo(1);
  });

  it("maps a 90° Lance Z rotation to a 90° Three.js Y rotation", () => {
    // Lance Z is Three.js Y, so a rotation about Lance Z must become a rotation about Three.js Y.
    // 90° CCW about Z in Lance: [[0,-1,0],[1,0,0],[0,0,1]] → flat [0,-1,0, 1,0,0, 0,0,1]
    const q = lanceRotationToThree([0, -1, 0, 1, 0, 0, 0, 0, 1]);
    const HALF_SQRT2 = Math.SQRT2 / 2;
    expect(q.x).toBeCloseTo(0);
    expect(q.y).toBeCloseTo(HALF_SQRT2);
    expect(q.z).toBeCloseTo(0);
    expect(q.w).toBeCloseTo(HALF_SQRT2);
  });
});

// ─── bboxTransform ────────────────────────────────────────────────────────────

function makeBbox(overrides: Partial<LocalBBox3D>): LocalBBox3D {
  return {
    id: "bbox-1",
    record_id: "rec-1",
    entity_id: "ent-1",
    view_id: "view-1",
    coords: [0, 0, 0, 1, 1, 1],
    format: "xyzwhd",
    rotation: [1, 0, 0, 0, 1, 0, 0, 0, 1],
    is_normalized: false,
    ...overrides,
  };
}

describe("bboxTransform — xyzwhd", () => {
  it("converts the center position via lanceToThree", () => {
    const bbox = makeBbox({ coords: [1, 2, 3, 4, 5, 6], format: "xyzwhd" });
    const { position } = bboxTransform(bbox);
    expect(position).toEqual([1, 3, -2]);
  });

  it("applies the Lance→Three axis swap to extents: [w, d, h]", () => {
    // coords size = [Lance X-ext=4, Lance Y-ext=5, Lance Z-ext=6].
    // Three.js size: [Lance X-ext, Lance Z-ext, Lance Y-ext] = [4, 6, 5].
    const bbox = makeBbox({ coords: [0, 0, 0, 4, 5, 6], format: "xyzwhd" });
    const { size } = bboxTransform(bbox);
    expect(size).toEqual([4, 6, 5]);
  });
});

describe("bboxTransform — xyzxyz", () => {
  it("computes the center from the two corners", () => {
    const bbox = makeBbox({ coords: [0, 0, 0, 2, 4, 6], format: "xyzxyz" });
    const { position } = bboxTransform(bbox);
    // Lance center: (1, 2, 3) → lanceToThree → [1, 3, -2]
    expect(position).toEqual([1, 3, -2]);
  });

  it("applies the Lance→Three axis swap to extents: [sx, sz, sy]", () => {
    // coords: x span=2, y span=4, z span=6
    // Three.js size: [Lance X-ext, Lance Z-ext, Lance Y-ext] = [2, 6, 4]
    const bbox = makeBbox({ coords: [0, 0, 0, 2, 4, 6], format: "xyzxyz" });
    const { size } = bboxTransform(bbox);
    expect(size).toEqual([2, 6, 4]);
  });

  it("handles inverted corner ordering", () => {
    const bbox = makeBbox({ coords: [2, 4, 6, 0, 0, 0], format: "xyzxyz" });
    const { size } = bboxTransform(bbox);
    expect(size).toEqual([2, 6, 4]);
  });
});

// ─── threeQuaternionToLanceRotation ──────────────────────────────────────────

describe("threeQuaternionToLanceRotation", () => {
  it("returns identity matrix for identity quaternion", () => {
    const rot = threeQuaternionToLanceRotation(new THREE.Quaternion());
    const identity = [1, 0, 0, 0, 1, 0, 0, 0, 1];
    for (let i = 0; i < 9; i++) expect(rot[i]).toBeCloseTo(identity[i]);
  });

  it("round-trips with lanceRotationToThree for a 90° Z rotation", () => {
    // The 90° CCW about Lance Z matrix, in row-major:
    const lanceRot = [0, -1, 0, 1, 0, 0, 0, 0, 1];
    const q = lanceRotationToThree(lanceRot);
    const recovered = threeQuaternionToLanceRotation(q);
    for (let i = 0; i < 9; i++) expect(recovered[i]).toBeCloseTo(lanceRot[i]);
  });

  it("identity quaternion round-trips through lanceRotationToThree", () => {
    const q = new THREE.Quaternion();
    const rot = threeQuaternionToLanceRotation(q);
    const q2 = lanceRotationToThree(rot);
    expect(q2.x).toBeCloseTo(0);
    expect(q2.y).toBeCloseTo(0);
    expect(q2.z).toBeCloseTo(0);
    expect(q2.w).toBeCloseTo(1);
  });
});

// ─── threeBoxToLanceXYZWHD ───────────────────────────────────────────────────

describe("threeBoxToLanceXYZWHD", () => {
  it("inverts lanceToThree for the center: [tx, -tz, ty]", () => {
    // lanceToThree(1, 2, 3) = [1, 3, -2] → inverse must recover (1, 2, 3)
    const [lx, ly, lz] = threeBoxToLanceXYZWHD([1, 3, -2], [1, 1, 1]);
    expect(lx).toBeCloseTo(1);
    expect(ly).toBeCloseTo(2);
    expect(lz).toBeCloseTo(3);
  });

  it("swaps Three.js Y/Z extents back to Lance size_y/size_z", () => {
    // Three.js size [X=4, Y=5, Z=6] → Lance [X-ext=4, Y-ext=Three Z=6, Z-ext=Three Y=5].
    const coords = threeBoxToLanceXYZWHD([0, 0, 0], [4, 5, 6]);
    expect(coords[3]).toBeCloseTo(4); // Lance X-extent
    expect(coords[4]).toBeCloseTo(6); // Lance Y-extent (Three.js Z)
    expect(coords[5]).toBeCloseTo(5); // Lance Z-extent (Three.js Y, up)
  });

  it("round-trips with bboxTransform xyzwhd", () => {
    // bboxTransform(xyzwhd) maps Lance center → Three.js position and passes size through.
    // threeBoxToLanceXYZWHD must recover the original Lance coords exactly.
    const bbox = makeBbox({ coords: [1, 2, 3, 4, 5, 6], format: "xyzwhd" });
    const { position, size } = bboxTransform(bbox);
    const recovered = threeBoxToLanceXYZWHD(position, size);
    expect(recovered).toEqual([1, 2, 3, 4, 5, 6]);
  });
});
