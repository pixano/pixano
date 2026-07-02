/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import * as THREE from "three";
import type { OrbitControls as ThreeOrbitControls } from "three/examples/jsm/controls/OrbitControls.js";

import { threeBoxToLanceXYZWHD, threeQuaternionToLanceRotation } from "$lib/annotations/coordinateTransforms";

import {
  ARROW_DEFS,
  ARROW_UP,
  AXIS_UNIT_VECS,
  DEFAULT_BOX_SIZE_FRACTION,
  GIZMO_ARROW_GAP_FRACTION,
  GIZMO_ARROW_HEAD_FRACTION,
  GIZMO_ARROW_HEIGHT_FRACTION,
  GIZMO_ARROW_RADIUS_FRACTION,
  GIZMO_ARROW_SHAFT_RADIUS_FRACTION,
  GIZMO_RING_PADDING,
  GIZMO_TUBE_FRACTION,
  MIN_GEOMETRY_SIZE,
  RING_ATAN_AXES,
  RING_DEFS,
  RING_LOCAL_QUATS,
  TRANSLATE_ARROW_DEFS,
} from "./boxEditorConstants.js";
import type { BBoxRenderData, GizmoVisibility } from "./bbox3dTypes.js";

type DrawPhase = "idle" | "confirming" | "moving" | "resizing-face" | "rotating";

export class BoxEditor {
  // FSM state
  drawPhase = $state<DrawPhase>("idle");
  previewVisible = $state(false);
  previewCenter = $state<[number, number, number]>([0, 0, 0]);
  previewSize = $state<[number, number, number]>([0.01, 0.01, 0.01]);
  previewQuaternion = $state(new THREE.Quaternion());
  editingBoxId = $state<string | null>(null);
  moveMode = $state<"ground" | "axis">("ground");
  translateAxis = $state<0 | 1 | 2>(0);
  rotAxis = $state<0 | 1 | 2>(1);

  activeDragging = $derived(
    this.drawPhase === "moving" ||
    this.drawPhase === "resizing-face" ||
    this.drawPhase === "rotating",
  );

  // Geometry caches
  previewEdgesGeometry = $state<THREE.EdgesGeometry | null>(null);
  private _raycastBoxGeom = $state<THREE.BoxGeometry | null>(null);
  private _raycastRingGeoms = $state<THREE.TorusGeometry[] | null>(null);
  private _raycastArrowGeom = $state<THREE.CylinderGeometry | null>(null);

  // Gizmo derived sizes
  gizmoRingRadius = $derived(
    Math.hypot(this.previewSize[0], this.previewSize[1], this.previewSize[2]) / 2 * GIZMO_RING_PADDING,
  );
  gizmoTubeRadius = $derived(this.gizmoRingRadius * GIZMO_TUBE_FRACTION);
  arrowHeight = $derived(this.gizmoRingRadius * GIZMO_ARROW_HEIGHT_FRACTION);
  arrowRadius = $derived(this.gizmoRingRadius * GIZMO_ARROW_RADIUS_FRACTION);
  arrowHeadLength = $derived(this.arrowHeight * GIZMO_ARROW_HEAD_FRACTION);
  arrowShaftLength = $derived(this.arrowHeight * (1 - GIZMO_ARROW_HEAD_FRACTION));
  arrowShaftRadius = $derived(this.arrowRadius * GIZMO_ARROW_SHAFT_RADIUS_FRACTION);
  arrowShaftOffsetY = $derived(-this.arrowHeight * GIZMO_ARROW_HEAD_FRACTION / 2);
  arrowHeadOffsetY = $derived(this.arrowHeight * (1 - GIZMO_ARROW_HEAD_FRACTION) / 2);

  // Gizmo derived world-space positions / orientations
  private readonly _ringWorldQuat = new THREE.Quaternion();
  private readonly _arrowWorldDir = new THREE.Vector3();
  private readonly _arrowFaceCenter = new THREE.Vector3();
  private readonly _arrowPos = new THREE.Vector3();
  private readonly _arrowRotQuat = new THREE.Quaternion();
  private readonly _translateArrowWorldDir = new THREE.Vector3();
  private readonly _translateArrowPos = new THREE.Vector3();
  private readonly _translateArrowRotQuat = new THREE.Quaternion();

  ringGizmos = $derived(
    RING_DEFS.map((ring, i) => {
      this._ringWorldQuat.multiplyQuaternions(this.previewQuaternion, RING_LOCAL_QUATS[i]);
      return {
        color: ring.color,
        quat: [this._ringWorldQuat.x, this._ringWorldQuat.y, this._ringWorldQuat.z, this._ringWorldQuat.w] as [number, number, number, number],
      };
    }),
  );

  arrowGizmos = $derived(
    (() => {
      const gap = this.gizmoRingRadius * GIZMO_ARROW_GAP_FRACTION;
      const hs = gap + this.arrowHeight / 2;
      return ARROW_DEFS.map((def) => {
        const halfSize = this.previewSize[def.axis] / 2;
        this._arrowWorldDir.copy(def.localDir).applyQuaternion(this.previewQuaternion).normalize();
        this._arrowFaceCenter.set(...this.previewCenter).addScaledVector(this._arrowWorldDir, halfSize);
        this._arrowPos.copy(this._arrowFaceCenter).addScaledVector(this._arrowWorldDir, hs);
        this._arrowRotQuat.setFromUnitVectors(ARROW_UP, this._arrowWorldDir);
        return {
          id: def.id,
          pos: [this._arrowPos.x, this._arrowPos.y, this._arrowPos.z] as [number, number, number],
          quat: [this._arrowRotQuat.x, this._arrowRotQuat.y, this._arrowRotQuat.z, this._arrowRotQuat.w] as [number, number, number, number],
          color: def.color,
          axis: def.axis,
          sign: def.sign,
        };
      });
    })(),
  );

  translateArrowGizmos = $derived(
    (() => {
      const hs = this.arrowHeight / 2;
      return TRANSLATE_ARROW_DEFS.map((def) => {
        this._translateArrowWorldDir.copy(def.localDir).applyQuaternion(this.previewQuaternion).normalize();
        this._translateArrowPos.set(...this.previewCenter).addScaledVector(this._translateArrowWorldDir, hs);
        this._translateArrowRotQuat.setFromUnitVectors(ARROW_UP, this._translateArrowWorldDir);
        return {
          id: def.id,
          pos: [this._translateArrowPos.x, this._translateArrowPos.y, this._translateArrowPos.z] as [number, number, number],
          quat: [this._translateArrowRotQuat.x, this._translateArrowRotQuat.y, this._translateArrowRotQuat.z, this._translateArrowRotQuat.w] as [number, number, number, number],
          color: def.color,
          axis: def.axis,
        };
      });
    })(),
  );

  rotWorldAngleDeg = $derived(
    2 * Math.atan2(
      [this.previewQuaternion.x, this.previewQuaternion.y, this.previewQuaternion.z][this.rotAxis],
      this.previewQuaternion.w,
    ) * (180 / Math.PI),
  );

  // Pre-allocated raycast meshes
  private readonly _raycastBoxMesh = new THREE.Mesh();
  private readonly _raycastRingMeshes = [new THREE.Mesh(), new THREE.Mesh(), new THREE.Mesh()];
  private readonly _raycastArrowMesh = new THREE.Mesh();
  // Unit cube scaled per bbox, so existing-box raycasts allocate no geometry
  private readonly _raycastExistingBoxMesh = new THREE.Mesh(new THREE.BoxGeometry(1, 1, 1));

  // Raycast scratch
  private readonly _raycastNdc = new THREE.Vector2();
  private readonly _raycastRay = new THREE.Raycaster();
  private readonly _screenNdc = new THREE.Vector2();
  private readonly _screenRay = new THREE.Raycaster();
  private readonly _groundPlane = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0);
  private readonly _screenGroundHit = new THREE.Vector3();

  // Ring-angle scratch
  private readonly _ringCenter = new THREE.Vector3();
  private readonly _ringPlane = new THREE.Plane();
  private readonly _ringHit = new THREE.Vector3();
  private readonly _ringNormal = new THREE.Vector3();

  // Drag-phase state
  private readonly _rotDeltaQ = new THREE.Quaternion();
  private readonly _rotAxisWorld = new THREE.Vector3();
  private readonly _invRotStartQuat = new THREE.Quaternion();
  private rotStartAngle = 0;
  private rotStartQuaternion = new THREE.Quaternion();

  private readonly _resizeF = new THREE.Vector3();
  private readonly _resizePlaneNormal = new THREE.Vector3();
  private readonly _resizeDragPlane = new THREE.Plane();
  private readonly _resizeHitPt = new THREE.Vector3();
  private _resizeWorldDir = new THREE.Vector3(0, 1, 0);
  private _resizeStartFaceCenter = new THREE.Vector3();
  private resizeAxis: 0 | 1 | 2 = 1;
  private resizeStartCenter: [number, number, number] = [0, 0, 0];
  private resizeStartSize: [number, number, number] = [0.01, 0.01, 0.01];
  private moveStartGround: THREE.Vector3 | null = null;
  private moveStartCenter: [number, number, number] = [0, 0, 0];

  private _prevDrawMode = false;

  constructor(
    private readonly camera: { current: THREE.PerspectiveCamera },
    private readonly getControlsRef: () => ThreeOrbitControls | null,
    private readonly getBboxes: () => BBoxRenderData[],
    private readonly getDrawMode: () => boolean,
    private readonly getFloorY: () => number,
    private readonly getCameraTarget: () => [number, number, number],
    private readonly getOrbitCenterDist: () => number,
    private readonly getGizmoVisibility: () => GizmoVisibility,
    private readonly onReadyToConfirm?: (
      coords: [number, number, number, number, number, number],
      rotation?: number[],
      editingId?: string,
    ) => void,
    private readonly onDrawCanceled?: () => void,
  ) {
    $effect(() => {
      const [w, h, d] = this.previewSize;
      const box = new THREE.BoxGeometry(w, h, d);
      const edges = new THREE.EdgesGeometry(box);
      this.previewEdgesGeometry = edges;
      this._raycastBoxGeom = box;
      this._raycastBoxMesh.geometry = box;
      return () => { edges.dispose(); box.dispose(); };
    });

    $effect(() => {
      const r = this.gizmoRingRadius;
      const tube = this.gizmoTubeRadius;
      const geoms = [0, 1, 2].map(() => new THREE.TorusGeometry(r, tube, 6, 64));
      this._raycastRingGeoms = geoms;
      geoms.forEach((g, i) => (this._raycastRingMeshes[i].geometry = g));
      return () => geoms.forEach((g) => g.dispose());
    });

    $effect(() => {
      const geom = new THREE.CylinderGeometry(this.arrowRadius, this.arrowRadius, this.arrowHeight, 8);
      this._raycastArrowGeom = geom;
      this._raycastArrowMesh.geometry = geom;
      return () => geom.dispose();
    });

    $effect(() => {
      const mode = this.getDrawMode();
      if (mode === this._prevDrawMode) return;
      this._prevDrawMode = mode;
      if (this.drawPhase !== "idle") this.reset();
    });

    $effect(() => {
      const ref = this.getControlsRef();
      if (!ref) return;
      void this.getDrawMode();

      const el = ref.domElement;
      if (!el) return;

      const setupRay = (clientX: number, clientY: number) => {
        const rect = el.getBoundingClientRect();
        this._raycastNdc.set(
          ((clientX - rect.left) / rect.width) * 2 - 1,
          -((clientY - rect.top) / rect.height) * 2 + 1,
        );
        this._raycastRay.setFromCamera(this._raycastNdc, this.camera.current);
      };

      const raycastBox = (clientX: number, clientY: number): THREE.Intersection | null => {
        if (!this.previewVisible || !this._raycastBoxGeom) return null;
        setupRay(clientX, clientY);
        this._raycastBoxMesh.position.set(...this.previewCenter);
        this._raycastBoxMesh.quaternion.copy(this.previewQuaternion);
        this._raycastBoxMesh.updateMatrixWorld(true);
        const hits = this._raycastRay.intersectObject(this._raycastBoxMesh);
        return hits.length > 0 ? hits[0] : null;
      };

      const raycastRings = (clientX: number, clientY: number): { axis: 0 | 1 | 2 } | null => {
        if (!this.previewVisible || !this.getGizmoVisibility().rings || !this._raycastRingGeoms) return null;
        setupRay(clientX, clientY);
        for (let axis = 0; axis < 3; axis++) {
          const mesh = this._raycastRingMeshes[axis];
          const q = this.ringGizmos[axis].quat;
          mesh.position.set(...this.previewCenter);
          mesh.quaternion.set(q[0], q[1], q[2], q[3]);
          mesh.updateMatrixWorld(true);
          if (this._raycastRay.intersectObject(mesh).length > 0) return { axis: axis as 0 | 1 | 2 };
        }
        return null;
      };

      const raycastExistingBoxes = (clientX: number, clientY: number): BBoxRenderData | null => {
        setupRay(clientX, clientY);
        let closestDist = Infinity;
        let closestBox: BBoxRenderData | null = null;
        for (const bbox of this.getBboxes()) {
          if (bbox.id === this.editingBoxId) continue;
          const { x, y, z, w } = bbox.quaternion;
          const mesh = this._raycastExistingBoxMesh;
          mesh.position.set(...bbox.position);
          mesh.quaternion.set(x, y, z, w);
          mesh.scale.set(bbox.size[0], bbox.size[1], bbox.size[2]);
          mesh.updateMatrixWorld(true);
          const hits = this._raycastRay.intersectObject(mesh);
          if (hits.length > 0 && hits[0].distance < closestDist) {
            closestDist = hits[0].distance;
            closestBox = bbox;
          }
        }
        return closestBox;
      };

      const computeRingAngle = (clientX: number, clientY: number, axis: 0 | 1 | 2): number | null => {
        setupRay(clientX, clientY);
        const normal = this._ringNormal.copy(AXIS_UNIT_VECS[axis]).applyQuaternion(this.rotStartQuaternion);
        this._ringCenter.set(...this.previewCenter);
        this._ringPlane.set(normal, -this._ringCenter.dot(normal));
        if (!this._raycastRay.ray.intersectPlane(this._ringPlane, this._ringHit)) return null;
        const d = this._ringHit.sub(this._ringCenter).applyQuaternion(this._invRotStartQuat);
        const [a, b] = RING_ATAN_AXES[axis];
        return Math.atan2(d.getComponent(a), d.getComponent(b));
      };

      const raycastArrows = (clientX: number, clientY: number) => {
        if (!this.previewVisible || !this.getGizmoVisibility().resizeArrows || !this._raycastArrowGeom) return null;
        setupRay(clientX, clientY);
        for (const arrow of this.arrowGizmos) {
          this._raycastArrowMesh.position.set(...arrow.pos);
          this._raycastArrowMesh.quaternion.set(...arrow.quat);
          this._raycastArrowMesh.updateMatrixWorld(true);
          if (this._raycastRay.intersectObject(this._raycastArrowMesh).length > 0) return arrow;
        }
        return null;
      };

      const raycastTranslateArrows = (clientX: number, clientY: number) => {
        if (!this.previewVisible || !this.getGizmoVisibility().translateArrows || !this._raycastArrowGeom) return null;
        setupRay(clientX, clientY);
        for (const arrow of this.translateArrowGizmos) {
          this._raycastArrowMesh.position.set(...arrow.pos);
          this._raycastArrowMesh.quaternion.set(...arrow.quat);
          this._raycastArrowMesh.updateMatrixWorld(true);
          if (this._raycastRay.intersectObject(this._raycastArrowMesh).length > 0) return arrow;
        }
        return null;
      };

      const screenToGround = (clientX: number, clientY: number): THREE.Vector3 | null => {
        const rect = el.getBoundingClientRect();
        this._screenNdc.set(
          ((clientX - rect.left) / rect.width) * 2 - 1,
          -((clientY - rect.top) / rect.height) * 2 + 1,
        );
        this._screenRay.setFromCamera(this._screenNdc, this.camera.current);
        this._groundPlane.constant = -this.getFloorY();
        return this._screenRay.ray.intersectPlane(this._groundPlane, this._screenGroundHit)
          ? this._screenGroundHit : null;
      };

      const onPointerDown = (e: PointerEvent) => {
        if (e.button !== 0 || !el.contains(e.target as Node)) return;

        if (this.drawPhase === "idle") {
          if (!this.getDrawMode()) return;
          e.stopPropagation(); e.preventDefault();
          const existing = raycastExistingBoxes(e.clientX, e.clientY);
          if (existing) { this._startEditingBox(existing); return; }
          const side = this.getOrbitCenterDist() * DEFAULT_BOX_SIZE_FRACTION;
          this.previewCenter = [...this.getCameraTarget()];
          this.previewSize = [side, side, side];
          this.previewQuaternion = new THREE.Quaternion();
          this.previewVisible = true;
          this.editingBoxId = null;
          this._fireReadyToConfirm();
          this.drawPhase = "confirming";

        } else if (this.drawPhase === "confirming") {
          const ringHit = raycastRings(e.clientX, e.clientY);
          if (ringHit) {
            e.stopPropagation(); e.preventDefault();
            this.rotAxis = ringHit.axis;
            this.rotStartQuaternion = this.previewQuaternion.clone();
            this._invRotStartQuat.copy(this.rotStartQuaternion).invert();
            this._rotAxisWorld.copy(AXIS_UNIT_VECS[this.rotAxis]).applyQuaternion(this.rotStartQuaternion);
            this.rotStartAngle = computeRingAngle(e.clientX, e.clientY, ringHit.axis) ?? 0;
            this.drawPhase = "rotating";
            return;
          }
          const translateHit = raycastTranslateArrows(e.clientX, e.clientY);
          if (translateHit) {
            e.stopPropagation(); e.preventDefault();
            this.translateAxis = translateHit.axis;
            this.moveMode = "axis";
            this.moveStartCenter = [...this.previewCenter];
            this._resizeWorldDir.set(0, 0, 0).setComponent(this.translateAxis, 1).applyQuaternion(this.previewQuaternion).normalize();
            this.drawPhase = "moving";
            return;
          }
          const arrowHit = raycastArrows(e.clientX, e.clientY);
          if (arrowHit) {
            e.stopPropagation(); e.preventDefault();
            this.resizeAxis = arrowHit.axis as 0 | 1 | 2;
            this.resizeStartCenter = [...this.previewCenter];
            this.resizeStartSize = [...this.previewSize];
            this._resizeWorldDir.set(0, 0, 0).setComponent(arrowHit.axis, arrowHit.sign);
            this._resizeWorldDir.applyQuaternion(this.previewQuaternion).normalize();
            this._resizeStartFaceCenter.fromArray(this.previewCenter).addScaledVector(this._resizeWorldDir, this.previewSize[arrowHit.axis] / 2);
            this.drawPhase = "resizing-face";
            return;
          }
          if (!raycastBox(e.clientX, e.clientY)) return;
          e.stopPropagation(); e.preventDefault();
          this.moveMode = "ground";
          const ground = screenToGround(e.clientX, e.clientY);
          if (!ground) return;
          this.moveStartGround = ground.clone();
          this.moveStartCenter = [...this.previewCenter];
          this.drawPhase = "moving";
        }
      };

      const onPointerMove = (e: PointerEvent) => {
        if (this.drawPhase === "rotating") {
          e.stopPropagation();
          const angle = computeRingAngle(e.clientX, e.clientY, this.rotAxis);
          if (angle === null) return;
          this._rotDeltaQ.setFromAxisAngle(this._rotAxisWorld, angle - this.rotStartAngle);
          this.previewQuaternion = new THREE.Quaternion().multiplyQuaternions(this._rotDeltaQ, this.rotStartQuaternion);

        } else if (this.drawPhase === "moving") {
          e.stopPropagation();
          if (this.moveMode === "axis") {
            const C = this._resizeWorldDir;
            this.camera.current.getWorldDirection(this._resizeF);
            this._resizePlaneNormal.copy(this._resizeF).addScaledVector(C, -this._resizeF.dot(C));
            if (this._resizePlaneNormal.lengthSq() < 1e-6) {
              this._resizePlaneNormal.set(Math.abs(C.y) > 0.99 ? 1 : 0, Math.abs(C.y) > 0.99 ? 0 : 1, 0);
            }
            this._resizePlaneNormal.normalize();
            this._ringCenter.set(...this.moveStartCenter);
            this._resizeDragPlane.setFromNormalAndCoplanarPoint(this._resizePlaneNormal, this._ringCenter);
            setupRay(e.clientX, e.clientY);
            if (!this._raycastRay.ray.intersectPlane(this._resizeDragPlane, this._resizeHitPt)) return;
            const drag = this._resizeHitPt.sub(this._ringCenter).dot(C);
            this.previewCenter = [
              this.moveStartCenter[0] + C.x * drag,
              this.moveStartCenter[1] + C.y * drag,
              this.moveStartCenter[2] + C.z * drag,
            ];
          } else {
            const hit = screenToGround(e.clientX, e.clientY);
            if (hit && this.moveStartGround) {
              this.previewCenter = [
                this.moveStartCenter[0] + hit.x - this.moveStartGround.x,
                this.previewCenter[1],
                this.moveStartCenter[2] + hit.z - this.moveStartGround.z,
              ];
            }
          }

        } else if (this.drawPhase === "resizing-face") {
          e.stopPropagation();
          const C = this._resizeWorldDir;
          this.camera.current.getWorldDirection(this._resizeF);
          this._resizePlaneNormal.copy(this._resizeF).addScaledVector(C, -this._resizeF.dot(C));
          if (this._resizePlaneNormal.lengthSq() < 1e-6) {
            this._resizePlaneNormal.set(Math.abs(C.y) > 0.99 ? 1 : 0, Math.abs(C.y) > 0.99 ? 0 : 1, 0);
          }
          this._resizePlaneNormal.normalize();
          this._resizeDragPlane.setFromNormalAndCoplanarPoint(this._resizePlaneNormal, this._resizeStartFaceCenter);
          setupRay(e.clientX, e.clientY);
          if (!this._raycastRay.ray.intersectPlane(this._resizeDragPlane, this._resizeHitPt)) return;
          const drag = this._resizeHitPt.sub(this._resizeStartFaceCenter).dot(C);
          const newSize = [...this.resizeStartSize] as [number, number, number];
          const newCenter = [...this.resizeStartCenter] as [number, number, number];
          newSize[this.resizeAxis] = Math.max(MIN_GEOMETRY_SIZE, this.resizeStartSize[this.resizeAxis] + drag);
          newCenter[0] = this.resizeStartCenter[0] + C.x * drag / 2;
          newCenter[1] = this.resizeStartCenter[1] + C.y * drag / 2;
          newCenter[2] = this.resizeStartCenter[2] + C.z * drag / 2;
          this.previewSize = newSize;
          this.previewCenter = newCenter;

        } else if (this.drawPhase === "confirming") {
          if (raycastRings(e.clientX, e.clientY)) {
            el.style.cursor = "grab";
          } else if (raycastTranslateArrows(e.clientX, e.clientY)) {
            el.style.cursor = "move";
          } else {
            const ah = raycastArrows(e.clientX, e.clientY);
            if (ah) {
              el.style.cursor = ah.axis === 1 ? "ns-resize" : ah.axis === 0 ? "ew-resize" : "nesw-resize";
            } else {
              el.style.cursor = raycastBox(e.clientX, e.clientY) ? "grab" : this.getDrawMode() ? "crosshair" : "default";
            }
          }
        } else {
          el.style.cursor = this.getDrawMode() ? "crosshair" : "default";
        }
      };

      const onPointerUp = (e: PointerEvent) => {
        if (e.button !== 0) return;
        if (this.drawPhase === "rotating") {
          this.drawPhase = "confirming";
          this._fireReadyToConfirm();
        } else if (this.drawPhase === "moving") {
          this.moveMode = "ground";
          this.drawPhase = "confirming";
          this._fireReadyToConfirm();
        } else if (this.drawPhase === "resizing-face") {
          this.drawPhase = "confirming";
          this._fireReadyToConfirm();
        }
      };

      window.addEventListener("pointerdown", onPointerDown, { capture: true });
      window.addEventListener("pointermove", onPointerMove, { capture: true });
      window.addEventListener("pointerup", onPointerUp, { capture: true });

      return () => {
        window.removeEventListener("pointerdown", onPointerDown, { capture: true });
        window.removeEventListener("pointermove", onPointerMove, { capture: true });
        window.removeEventListener("pointerup", onPointerUp, { capture: true });
        el.style.cursor = "";
      };
    });

    $effect(() => {
      const onKeyDown = (e: KeyboardEvent) => {
        const t = e.target as HTMLElement | null;
        if (t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.isContentEditable)) return;
        if (e.key === "Escape") { e.preventDefault(); this.reset(); }
      };
      window.addEventListener("keydown", onKeyDown);
      return () => window.removeEventListener("keydown", onKeyDown);
    });
  }

  reset(): void {
    this.drawPhase = "idle";
    this.previewVisible = false;
    this.moveStartGround = null;
    this.previewQuaternion = new THREE.Quaternion();
    this.editingBoxId = null;
    this.onDrawCanceled?.();
  }

  private _startEditingBox(bbox: BBoxRenderData): void {
    const { x, y, z, w } = bbox.quaternion;
    this.previewCenter = bbox.position;
    this.previewSize = bbox.size;
    this.previewQuaternion = new THREE.Quaternion(x, y, z, w);
    this.previewVisible = true;
    this.editingBoxId = bbox.id;
    this.drawPhase = "confirming";
    this.onReadyToConfirm?.(
      threeBoxToLanceXYZWHD(bbox.position, bbox.size),
      threeQuaternionToLanceRotation(this.previewQuaternion),
      bbox.id,
    );
  }

  private _fireReadyToConfirm(): void {
    this.onReadyToConfirm?.(
      threeBoxToLanceXYZWHD(this.previewCenter, this.previewSize),
      threeQuaternionToLanceRotation(this.previewQuaternion),
      this.editingBoxId ?? undefined,
    );
  }
}
