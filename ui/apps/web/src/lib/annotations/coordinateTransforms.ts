/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import * as THREE from "three";

import type { BBox3DGeometry } from "$lib/annotations/annotationCollection.svelte.js";

// S maps Lance coords → Three.js coords: lanceToThree(x,y,z) = [x, z, -y].
// Correct change of basis for rotation matrices: R_three = S * R_lance * S⁻¹ = S * R_lance * Sᵀ
const _S = new THREE.Matrix4().set(1, 0, 0, 0, 0, 0, 1, 0, 0, -1, 0, 0, 0, 0, 0, 1);
const _ST = new THREE.Matrix4().copy(_S).transpose();

export function lanceToThree(x: number, y: number, z: number): [number, number, number] {
  return [x, z, -y];
}

export function lanceRotationToThree(rotation: number[] | undefined): THREE.Quaternion {
  const m = new THREE.Matrix4();
  if (rotation && rotation.length === 9) {
    const r = rotation;
    m.set(r[0], r[1], r[2], 0, r[3], r[4], r[5], 0, r[6], r[7], r[8], 0, 0, 0, 0, 1);
  }
  const composed = new THREE.Matrix4().multiplyMatrices(_S, m).multiply(_ST);
  return new THREE.Quaternion().setFromRotationMatrix(composed);
}

export function bboxTransform(bbox: BBox3DGeometry): {
  position: [number, number, number];
  size: [number, number, number];
  quaternion: THREE.Quaternion;
} {
  const c = bbox.coords;
  if (bbox.format === "xyzxyz") {
    const cx = (c[0] + c[3]) / 2;
    const cy = (c[1] + c[4]) / 2;
    const cz = (c[2] + c[5]) / 2;
    const sx = Math.abs(c[3] - c[0]);
    const sy = Math.abs(c[4] - c[1]);
    const sz = Math.abs(c[5] - c[2]);
    return {
      position: lanceToThree(cx, cy, cz),
      // Lance extents: sx=X, sy=Y, sz=Z. Three.js axes: X=LanceX, Y=LanceZ, Z=LanceY.
      size: [sx, sz, sy],
      quaternion: lanceRotationToThree(bbox.rotation),
    };
  }
  // xyzwhd: center (x,y,z) + extents (w,h,d) along Lance axes X, Y, Z — the
  // exact convention the backend uses to build the box corners
  // (BBox3D.get_3dbbox_corners). Same axis swap as xyzxyz: the Lance Z-extent
  // (c[5]) is the up direction and must land on Three.js Y.
  return {
    position: lanceToThree(c[0], c[1], c[2]),
    size: [c[3], c[5], c[4]],
    quaternion: lanceRotationToThree(bbox.rotation),
  };
}

/**
 * Converts a Three.js quaternion back to a Lance 3×3 rotation matrix (row-major).
 *
 * lanceRotationToThree applies R_three = S * R_lance * S^T.
 * The inverse is:            R_lance = S^T * R_three * S
 *
 * where S is the Lance→Three axis-swap matrix:
 *   lanceToThree(x,y,z) = [x, z, -y]
 *   S = [[1,0,0],[0,0,1],[0,-1,0]]
 */
export function threeQuaternionToLanceRotation(q: THREE.Quaternion): number[] {
  const R_three = new THREE.Matrix4().makeRotationFromQuaternion(q);
  const R_lance = new THREE.Matrix4().multiplyMatrices(_ST, R_three).multiply(_S);
  const e = R_lance.elements; // Three.js stores elements column-major
  return [e[0], e[4], e[8], e[1], e[5], e[9], e[2], e[6], e[10]];
}

/**
 * Inverse of bboxTransform's xyzwhd path: converts a Three.js preview center
 * and size back to Lance xyzwhd coordinates for storage.
 *
 * lanceToThree(lx, ly, lz) = [lx, lz, -ly]
 * Inverse:  lx = three.x,  ly = -three.z,  lz = three.y
 *
 * Size mapping (inverse of bboxTransform's xyzwhd axis swap [c3, c5, c4]):
 *   Lance X-extent = Three.js X-extent, Lance Y-extent = Three.js Z-extent,
 *   Lance Z-extent = Three.js Y-extent. Stored as [w, d, h] so the Lance
 *   coords match the backend's own [size_x, size_y, size_z] convention.
 */
export function threeBoxToLanceXYZWHD(
  center: [number, number, number],
  size: [number, number, number],
): [number, number, number, number, number, number] {
  const [tx, ty, tz] = center;
  const [w, h, d] = size;
  return [tx, -tz, ty, w, d, h];
}
