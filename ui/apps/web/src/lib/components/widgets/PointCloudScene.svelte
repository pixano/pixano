<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { T, useThrelte } from "@threlte/core";
  import { HTML, OrbitControls } from "@threlte/extras";
  import { onMount } from "svelte";
  import * as THREE from "three";

  import { bboxTransform, threeBoxToLanceXYZWHD, threeQuaternionToLanceRotation } from "$lib/annotations/coordinateTransforms";
  import { parsePointCloud } from "$lib/annotations/pointCloudParser";
  import { pickEntityLabel } from "$lib/annotations/types";
  import type { LocalBBox3D } from "$lib/api/annotations";
  import type { OrbitControls as ThreeOrbitControls } from "three/examples/jsm/controls/OrbitControls.js";

  interface Props {
    pointCloudUrl?: string;
    bboxes3d?: LocalBBox3D[];
    drawMode?: boolean;
    cameraMode?: "orbit" | "first-person";
    /**
     * Fired when the user clicks to lock the height (transitions to "confirming"),
     * and again after each drag-move when in "moving" phase.
     * Parent stores the coords to show Save/Cancel UI.
     */
    onReadyToConfirm?: (coords: [number, number, number, number, number, number], rotation?: number[], editingId?: string) => void;
    /**
     * Fired when drawing is cancelled (Escape key, mode turned off, external reset).
     */
    onDrawCanceled?: () => void;
    /**
     * Fired when the point cloud fails to load. Parent is responsible for
     * surfacing the message to the user.
     */
    onLoadError?: (message: string) => void;
    /**
     * Parent increments this to force-reset the FSM (Cancel button).
     */
    externalReset?: number;
    /** Whether to show and enable the rotation gizmo rings. */
    showRings?: boolean;
    /** Whether to show and enable the resize arrow gizmos. */
    showArrows?: boolean;
  }

  let {
    pointCloudUrl,
    bboxes3d = [],
    drawMode = false,
    cameraMode = "orbit",
    onReadyToConfirm,
    onDrawCanceled,
    onLoadError,
    externalReset = 0,
    showRings = true,
    showArrows = true,
  }: Props = $props();

  let positions = $state<Float32Array>(new Float32Array(0));
  let colors = $state<Float32Array>(new Float32Array(0));
  let loading = $state(true);

  let cameraPosition = $state<[number, number, number]>([30, 20, 30]);
  let cameraTarget = $state<[number, number, number]>([0, 0, 0]);

  let controlsRef = $state<ThreeOrbitControls | null>(null);

  // Floor Y in Three.js space — updated after point cloud loads; used for ground raycasting
  let floorY = $state(0);

  const CAMERA_DISTANCE_FACTOR = 1.2;
  const CAMERA_HEIGHT_FACTOR = 0.5;
  const ORBIT_DAMPING_FACTOR = 0.07;
  const AMBIENT_LIGHT_INTENSITY = 0.6;
  const POINT_RENDER_SIZE = 0.05;
  const BOX_LINE_WIDTH = 2;
  const BOX_COLOR_PERSISTED = "#22d3ee";
  const BOX_COLOR_PREVIEW = "#f59e0b";
  const GRID_SIZE = 100;
  const GRID_DIVISIONS = 50;
  const GRID_COLOR_CENTER = "#333333";
  const GRID_COLOR_LINES = "#222222";

  const MIN_FOOTPRINT_SIZE = 0.05;
  const MIN_BOX_HEIGHT = 0.05;
  const MIN_GEOMETRY_SIZE = 0.01;
  const HEIGHT_DRAG_SCALE_PER_PX = 0.01;
  const HEIGHT_MINIMUM_FROM_FOOTPRINT_RATIO = 0.1;
  const WHEEL_LINE_HEIGHT_PX = 40;
  const FETCH_TIMEOUT_MS = 30_000;

  // Reused across every pointermove — avoids per-event allocations in hot paths
  const _screenNdc = new THREE.Vector2();
  const _screenRay = new THREE.Raycaster();
  const _groundPlane = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0);
  const _screenGroundHit = new THREE.Vector3();

  // Scratch objects for the draw-event $effect (raycast + drag handlers)
  const _raycastNdc = new THREE.Vector2();
  const _raycastRay = new THREE.Raycaster();
  // Unit vectors for ring-plane normals and rotation axes (index = axis: 0=X, 1=Y, 2=Z)
  const _AXIS_UNIT_VECS = [
    new THREE.Vector3(1, 0, 0),
    new THREE.Vector3(0, 1, 0),
    new THREE.Vector3(0, 0, 1),
  ] as const;
  // computeRingAngle scratch
  const _ringCenter = new THREE.Vector3();
  const _ringPlane = new THREE.Plane();
  const _ringHit = new THREE.Vector3();
  // rotating-phase scratch
  const _rotDeltaQ = new THREE.Quaternion();
  // resizing-face-phase scratch
  const _resizeF = new THREE.Vector3();
  const _resizePlaneNormal = new THREE.Vector3();
  const _resizeDragPlane = new THREE.Plane();
  const _resizeHitPt = new THREE.Vector3();
  // arrow-gizmos $derived scratch — hoisted to avoid per-derivation allocations
  const _arrowWorldDir = new THREE.Vector3();
  const _arrowFaceCenter = new THREE.Vector3();
  const _arrowPos = new THREE.Vector3();
  const _arrowRotQuat = new THREE.Quaternion();
  // Pre-allocated Mesh objects for raycasting — geometry is swapped in the $effects below.
  // Avoids allocating up to 10 Mesh objects per pointermove during the confirming phase.
  const _raycastBoxMesh = new THREE.Mesh();
  const _raycastRingMeshes = [new THREE.Mesh(), new THREE.Mesh(), new THREE.Mesh()];
  const _raycastArrowMesh = new THREE.Mesh();

  // ─── Draw FSM ─────────────────────────────────────────────────────────────────
  // idle → drawing-base → drawing-height → confirming ↔ moving | resizing-face

  type DrawPhase = "idle" | "drawing-base" | "drawing-height" | "confirming" | "moving" | "resizing-face" | "rotating";
  let drawPhase = $state<DrawPhase>("idle");
  let baseCornerA = $state<THREE.Vector3 | null>(null);
  let baseCornerB = $state<THREE.Vector3 | null>(null);
  let boxHeight = $state(0);
  let heightDragStartScreenY = $state(0);
  let previewVisible = $state(false);
  let previewCenter = $state<[number, number, number]>([0, 0, 0]);
  let previewSize = $state<[number, number, number]>([0.01, 0.01, 0.01]);

  // Pre-built geometries for the preview box — recreated only when previewSize changes.
  // Box is kept alive for raycasting; EdgesGeometry is used for rendering.
  let previewEdgesGeometry = $state<THREE.EdgesGeometry | null>(null);
  let _raycastBoxGeom = $state<THREE.BoxGeometry | null>(null);
  $effect(() => {
    const [w, h, d] = previewSize;
    const box = new THREE.BoxGeometry(w, h, d);
    const edges = new THREE.EdgesGeometry(box);
    previewEdgesGeometry = edges;
    _raycastBoxGeom = box;
    _raycastBoxMesh.geometry = box;
    return () => { edges.dispose(); box.dispose(); };
  });

  // Current rotation of the preview box (Three.js world space)
  let previewQuaternion = $state(new THREE.Quaternion());

  // Id of the existing box being edited; null when drawing a new box
  let editingBoxId = $state<string | null>(null);

  const activeDragging = $derived(
    drawPhase === "drawing-base" ||
    drawPhase === "drawing-height" ||
    drawPhase === "moving" ||
    drawPhase === "resizing-face" ||
    drawPhase === "rotating"
  );

  // Gizmo rings — radius = bounding sphere * padding
  const GIZMO_RING_PADDING = 1.2;
  const GIZMO_TUBE_FRACTION = 0.0225;
  let gizmoRingRadius = $derived(
    Math.hypot(previewSize[0], previewSize[1], previewSize[2]) / 2 * GIZMO_RING_PADDING,
  );
  let gizmoTubeRadius = $derived(gizmoRingRadius * GIZMO_TUBE_FRACTION);

  // Ring definitions: euler so each ring lies in the correct plane, plus render color.
  // Axis 0=X (YZ plane), 1=Y (XZ plane), 2=Z (XY plane).
  const RING_DEFS = [
    { color: "#ef4444", euler: new THREE.Euler(0, Math.PI / 2, 0) },
    { color: "#22c55e", euler: new THREE.Euler(Math.PI / 2, 0, 0) },
    { color: "#3b82f6", euler: new THREE.Euler(0, 0, 0) },
  ] as const;
  // Component indices [a, b] for Math.atan2(d.component_a, d.component_b) per axis.
  const RING_ATAN_AXES = [[2, 1], [2, 0], [1, 0]] as const;

  // Resize arrows — shaft + arrowhead per face, matching ring colour scheme (X=red, Y=green, Z=blue)
  const GIZMO_ARROW_HEIGHT_FRACTION = 0.50;
  const GIZMO_ARROW_RADIUS_FRACTION = 0.09;
  const GIZMO_ARROW_GAP_FRACTION = 0.04;
  const GIZMO_ARROW_HEAD_FRACTION = 0.42;   // fraction of total height that is the cone head
  const GIZMO_ARROW_SHAFT_RADIUS_FRACTION = 0.30; // shaft radius as fraction of head radius
  const arrowHeight = $derived(gizmoRingRadius * GIZMO_ARROW_HEIGHT_FRACTION);
  const arrowRadius = $derived(gizmoRingRadius * GIZMO_ARROW_RADIUS_FRACTION);
  const arrowHeadLength = $derived(arrowHeight * GIZMO_ARROW_HEAD_FRACTION);
  const arrowShaftLength = $derived(arrowHeight * (1 - GIZMO_ARROW_HEAD_FRACTION));
  const arrowShaftRadius = $derived(arrowRadius * GIZMO_ARROW_SHAFT_RADIUS_FRACTION);
  // Local Y offsets within the arrow group (group origin = center of full arrow)
  const arrowShaftOffsetY = $derived(-arrowHeight * GIZMO_ARROW_HEAD_FRACTION / 2);
  const arrowHeadOffsetY = $derived(arrowHeight * (1 - GIZMO_ARROW_HEAD_FRACTION) / 2);
  // Precomputed per-frame data for each of the 6 face arrows.
  // Directions are computed in local box space then rotated by previewQuaternion so
  // the cones always point perpendicular to their actual face regardless of rotation.
  const _ARROW_UP = new THREE.Vector3(0, 1, 0);
  const _ARROW_DEFS = [
    { id: "+x", localDir: new THREE.Vector3( 1,  0,  0), color: "#ef4444", axis: 0 as const, sign:  1 as const },
    { id: "-x", localDir: new THREE.Vector3(-1,  0,  0), color: "#ef4444", axis: 0 as const, sign: -1 as const },
    { id: "+y", localDir: new THREE.Vector3( 0,  1,  0), color: "#22c55e", axis: 1 as const, sign:  1 as const },
    { id: "-y", localDir: new THREE.Vector3( 0, -1,  0), color: "#22c55e", axis: 1 as const, sign: -1 as const },
    { id: "+z", localDir: new THREE.Vector3( 0,  0,  1), color: "#3b82f6", axis: 2 as const, sign:  1 as const },
    { id: "-z", localDir: new THREE.Vector3( 0,  0, -1), color: "#3b82f6", axis: 2 as const, sign: -1 as const },
  ] as const;
  const arrowGizmos = $derived(
    (() => {
      const gap = gizmoRingRadius * GIZMO_ARROW_GAP_FRACTION;
      const hs = gap + arrowHeight / 2;
      return _ARROW_DEFS.map((def) => {
        const halfSize = previewSize[def.axis] / 2;
        _arrowWorldDir.copy(def.localDir).applyQuaternion(previewQuaternion).normalize();
        _arrowFaceCenter.set(...previewCenter).addScaledVector(_arrowWorldDir, halfSize);
        _arrowPos.copy(_arrowFaceCenter).addScaledVector(_arrowWorldDir, hs);
        _arrowRotQuat.setFromUnitVectors(_ARROW_UP, _arrowWorldDir);
        return {
          id: def.id,
          pos: [_arrowPos.x, _arrowPos.y, _arrowPos.z] as [number, number, number],
          quat: [_arrowRotQuat.x, _arrowRotQuat.y, _arrowRotQuat.z, _arrowRotQuat.w] as [number, number, number, number],
          color: def.color,
          axis: def.axis,
          sign: def.sign,
        };
      });
    })()
  );

  // Raycast geometries for rings and arrows — cached and rebuilt only when gizmo dimensions
  // change, avoiding geometry allocation on every pointermove during confirming phase.
  let _raycastRingGeoms = $state<THREE.TorusGeometry[] | null>(null);
  $effect(() => {
    const r = gizmoRingRadius;
    const tube = gizmoTubeRadius;
    const geoms = [0, 1, 2].map(() => new THREE.TorusGeometry(r, tube, 6, 64));
    _raycastRingGeoms = geoms;
    geoms.forEach((g, i) => (_raycastRingMeshes[i].geometry = g));
    return () => geoms.forEach((g) => g.dispose());
  });

  let _raycastArrowGeom = $state<THREE.CylinderGeometry | null>(null);
  $effect(() => {
    const geom = new THREE.CylinderGeometry(arrowRadius, arrowRadius, arrowHeight, 8);
    _raycastArrowGeom = geom;
    _raycastArrowMesh.geometry = geom;
    return () => geom.dispose();
  });

  // Move phase
  let moveStartGround: THREE.Vector3 | null = null;
  let moveStartCenter: [number, number, number] = [0, 0, 0];

  // Resize-face phase — which face is being dragged and its initial geometry
  let resizeAxis: 0 | 1 | 2 = 1;
  let resizeStartCenter: [number, number, number] = [0, 0, 0];
  let resizeStartSize: [number, number, number] = [0.01, 0.01, 0.01];
  // World-space face normal and face center snapshotted at drag start — per-drag state, not permanent scratch.
  let _resizeWorldDir = new THREE.Vector3(0, 1, 0);
  let _resizeStartFaceCenter = new THREE.Vector3();

  // Rotating phase — which ring axis is being dragged
  let rotAxis: 0 | 1 | 2 = 1;
  let rotStartAngle = 0;
  let rotStartQuaternion = new THREE.Quaternion();

  const { camera } = useThrelte();

  // ─── OrbitControls configuration (single source of truth) ───────────────────
  // Drives all OrbitControls properties reactively based on cameraMode and
  // drawPhase. Custom handlers below add only what OrbitControls can't do alone.

  $effect(() => {
    const ref = controlsRef;
    if (!ref) return;

    if (cameraMode === "orbit") {
      // Orbit mode: left-drag = orbit, right-drag = pan, scroll = zoom.
      // These are Three.js OrbitControls defaults and work reliably across platforms.
      ref.enableRotate = !activeDragging;
      ref.enableZoom = !activeDragging;
      ref.enablePan = !activeDragging;
      ref.screenSpacePanning = true;
      ref.mouseButtons = activeDragging
        ? { LEFT: null, MIDDLE: null, RIGHT: null }
        : { LEFT: THREE.MOUSE.ROTATE, MIDDLE: THREE.MOUSE.DOLLY, RIGHT: THREE.MOUSE.PAN };
    } else {
      // First-person mode: OrbitControls handles left-pan only. Right-drag and
      // scroll are managed by the custom first-person effect below.
      ref.enableRotate = false;
      ref.enableZoom = false;
      ref.enablePan = !activeDragging;
      ref.screenSpacePanning = false;
      ref.mouseButtons = activeDragging
        ? { LEFT: null, MIDDLE: null, RIGHT: null }
        : { LEFT: THREE.MOUSE.PAN, MIDDLE: null, RIGHT: null };
    }
  });

  // ─── Orbit mode: sync cameraTarget for the draw-phase overlay ───────────────────

  $effect(() => {
    const ref = controlsRef;
    if (!ref || cameraMode !== "orbit") return;

    const onChange = () => {
      cameraTarget = [ref.target.x, ref.target.y, ref.target.z];
    };
    ref.addEventListener("change", onChange);

    return () => {
      ref.removeEventListener("change", onChange);
    };
  });

  // ─── First-person mode: right-drag = look-around, scroll = fly-through ────────

  $effect(() => {
    const ref = controlsRef;
    if (!ref || cameraMode !== "first-person") return;

    const ROTATION_SENSITIVITY = 0.003;
    const FLY_SPEED = 0.05;
    let isRightDragging = false;
    let lastX = 0;
    let lastY = 0;

    const _worldUp = new THREE.Vector3(0, 1, 0);
    const _localRight = new THREE.Vector3(1, 0, 0);
    const _forward = new THREE.Vector3();
    const _flyDir = new THREE.Vector3();

    const onContextMenu = (e: MouseEvent) => e.preventDefault();

    const onPointerDown = (e: PointerEvent) => {
      if (e.button !== 2) return;
      if (activeDragging) return;
      isRightDragging = true;
      lastX = e.clientX;
      lastY = e.clientY;
    };

    const onPointerMove = (e: PointerEvent) => {
      if (!isRightDragging) return;
      const dx = e.clientX - lastX;
      const dy = e.clientY - lastY;
      lastX = e.clientX;
      lastY = e.clientY;

      const cam = ref.object as THREE.PerspectiveCamera;
      cam.rotateOnWorldAxis(_worldUp, -dx * ROTATION_SENSITIVITY);
      cam.rotateOnAxis(_localRight, -dy * ROTATION_SENSITIVITY);

      const dist = cam.position.distanceTo(ref.target);
      _forward.set(0, 0, -1).applyQuaternion(cam.quaternion);
      ref.target.copy(cam.position).addScaledVector(_forward, dist);
      cameraTarget = [ref.target.x, ref.target.y, ref.target.z];
      ref.update();
    };

    const onPointerUp = (e: PointerEvent) => {
      if (e.button === 2) isRightDragging = false;
    };

    // Sync cameraTarget when OrbitControls left-pan moves the camera
    const onChange = () => {
      cameraTarget = [ref.target.x, ref.target.y, ref.target.z];
    };
    ref.addEventListener("change", onChange);

    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      const cam = ref.object as THREE.PerspectiveCamera;
      cam.getWorldDirection(_flyDir);
      const delta = e.deltaMode === 1 ? e.deltaY * WHEEL_LINE_HEIGHT_PX : e.deltaY;
      cam.position.addScaledVector(_flyDir, -delta * FLY_SPEED);
      ref.target.addScaledVector(_flyDir, -delta * FLY_SPEED);
      cameraTarget = [ref.target.x, ref.target.y, ref.target.z];
      ref.update();
    };

    ref.domElement.addEventListener("contextmenu", onContextMenu);
    ref.domElement.addEventListener("pointerdown", onPointerDown);
    window.addEventListener("pointermove", onPointerMove);
    window.addEventListener("pointerup", onPointerUp);
    ref.domElement.addEventListener("wheel", onWheel, { passive: false });

    return () => {
      ref.domElement.removeEventListener("contextmenu", onContextMenu);
      ref.domElement.removeEventListener("pointerdown", onPointerDown);
      window.removeEventListener("pointermove", onPointerMove);
      window.removeEventListener("pointerup", onPointerUp);
      ref.domElement.removeEventListener("wheel", onWheel);
      ref.removeEventListener("change", onChange);
    };
  });

  // ─── Draw-mode pointer events ────────────────────────────────────────────────
  // All three handlers live on window (capture) so stopPropagation prevents the event
  // from reaching OrbitControls on the canvas element. onPointerDown guards with
  // el.contains(target) so toolbar and overlay clicks are never intercepted.

  $effect(() => {
    const ref = controlsRef;
    if (!ref) return;
    void drawMode; // reactive dependency: re-run (and reset cursor) when mode toggles

    const el: HTMLElement = ref.domElement;

    function setupRay(clientX: number, clientY: number): void {
      const rect = el.getBoundingClientRect();
      _raycastNdc.set(
        ((clientX - rect.left) / rect.width) * 2 - 1,
        -((clientY - rect.top) / rect.height) * 2 + 1,
      );
      _raycastRay.setFromCamera(_raycastNdc, camera.current);
    }

    function raycastBox(clientX: number, clientY: number): THREE.Intersection | null {
      if (!previewVisible || !_raycastBoxGeom) return null;
      setupRay(clientX, clientY);
      _raycastBoxMesh.position.set(...previewCenter);
      _raycastBoxMesh.quaternion.copy(previewQuaternion);
      _raycastBoxMesh.updateMatrixWorld(true);
      const hits = _raycastRay.intersectObject(_raycastBoxMesh);
      return hits.length > 0 ? hits[0] : null;
    }

    function raycastRings(clientX: number, clientY: number): { axis: 0 | 1 | 2 } | null {
      if (!previewVisible || !showRings || !_raycastRingGeoms) return null;
      setupRay(clientX, clientY);
      for (let axis = 0; axis < 3; axis++) {
        const mesh = _raycastRingMeshes[axis];
        mesh.position.set(...previewCenter);
        mesh.setRotationFromEuler(RING_DEFS[axis as 0 | 1 | 2].euler);
        mesh.updateMatrixWorld(true);
        const hits = _raycastRay.intersectObject(mesh);
        if (hits.length > 0) return { axis: axis as 0 | 1 | 2 };
      }
      return null;
    }

    // Raycasts against all rendered boxes and returns the closest one hit.
    // Used in navigate mode to let the user click an existing box to edit it.
    function raycastExistingBoxes(clientX: number, clientY: number): LocalBBox3D | null {
      setupRay(clientX, clientY);
      let closestDist = Infinity;
      let closestBox: LocalBBox3D | null = null;
      for (const bbox of bboxes3d) {
        if (bbox.id === editingBoxId) continue;
        const t = bboxTransform(bbox);
        const geom = new THREE.BoxGeometry(t.size[0], t.size[1], t.size[2]);
        const mesh = new THREE.Mesh(geom);
        mesh.position.set(t.position[0], t.position[1], t.position[2]);
        mesh.quaternion.copy(t.quaternion);
        mesh.updateMatrixWorld(true);
        const hits = _raycastRay.intersectObject(mesh);
        geom.dispose();
        if (hits.length > 0 && hits[0].distance < closestDist) {
          closestDist = hits[0].distance;
          closestBox = bbox;
        }
      }
      return closestBox;
    }

    // Returns the signed angle (atan2) of the mouse ray's intersection with the
    // ring plane, measured from the ring center in the ring's two tangent axes.
    function computeRingAngle(clientX: number, clientY: number, axis: 0 | 1 | 2): number | null {
      setupRay(clientX, clientY);
      const normal = _AXIS_UNIT_VECS[axis];
      _ringCenter.set(...previewCenter);
      _ringPlane.set(normal, -_ringCenter.dot(normal));
      if (!_raycastRay.ray.intersectPlane(_ringPlane, _ringHit)) return null;
      const d = _ringHit.sub(_ringCenter);
      const [a, b] = RING_ATAN_AXES[axis];
      return Math.atan2(d.getComponent(a), d.getComponent(b));
    }

    function raycastArrows(clientX: number, clientY: number) {
      if (!previewVisible || !showArrows || !_raycastArrowGeom) return null;
      setupRay(clientX, clientY);
      for (const arrow of arrowGizmos) {
        _raycastArrowMesh.position.set(arrow.pos[0], arrow.pos[1], arrow.pos[2]);
        _raycastArrowMesh.quaternion.set(arrow.quat[0], arrow.quat[1], arrow.quat[2], arrow.quat[3]);
        _raycastArrowMesh.updateMatrixWorld(true);
        const hits = _raycastRay.intersectObject(_raycastArrowMesh);
        if (hits.length > 0) return arrow;
      }
      return null;
    }

    const onPointerDown = (e: PointerEvent) => {
      if (e.button !== 0) return;
      // Only handle events that target the canvas — toolbar and overlay clicks must pass through.
      if (!el.contains(e.target as Node)) return;

      if (drawPhase === "idle") {
        if (drawMode) {
          const hit = screenToGround(e.clientX, e.clientY, el);
          if (!hit) return;
          e.stopPropagation();
          e.preventDefault();
          baseCornerA = hit.clone();
          baseCornerB = hit.clone();
          previewVisible = true;
          boxHeight = 0;
          drawPhase = "drawing-base";
        } else {
          const hit = raycastExistingBoxes(e.clientX, e.clientY);
          if (!hit) return;
          e.stopPropagation();
          e.preventDefault();
          startEditingBox(hit);
        }
      } else if (drawPhase === "drawing-height") {
        e.stopPropagation();
        e.preventDefault();
        if (boxHeight < MIN_BOX_HEIGHT) { resetDraw(); return; }
        fireReadyToConfirm();
        drawPhase = "confirming";
      } else if (drawPhase === "confirming") {
        // Rings take priority — they live outside the box so there's no overlap,
        // but checking first keeps the intent unambiguous.
        const ringHit = raycastRings(e.clientX, e.clientY);
        if (ringHit) {
          e.stopPropagation();
          e.preventDefault();
          rotAxis = ringHit.axis;
          rotStartAngle = computeRingAngle(e.clientX, e.clientY, ringHit.axis) ?? 0;
          rotStartQuaternion = previewQuaternion.clone();
          drawPhase = "rotating";
          return;
        }
        const arrowHit = raycastArrows(e.clientX, e.clientY);
        if (arrowHit) {
          e.stopPropagation();
          e.preventDefault();
          resizeAxis = arrowHit.axis as 0 | 1 | 2;
          resizeStartCenter = [...previewCenter];
          resizeStartSize = [...previewSize];
          // Snapshot the world-space face normal (local axis rotated by box quaternion)
          // and the face center so onPointerMove can project onto the correct plane.
          _resizeWorldDir.set(0, 0, 0).setComponent(arrowHit.axis, arrowHit.sign);
          _resizeWorldDir.applyQuaternion(previewQuaternion).normalize();
          _resizeStartFaceCenter.fromArray(previewCenter).addScaledVector(
            _resizeWorldDir, previewSize[arrowHit.axis] / 2,
          );
          drawPhase = "resizing-face";
          return;
        }
        const boxHit = raycastBox(e.clientX, e.clientY);
        if (!boxHit) {
          // In navigate mode, clicking another existing box switches to editing it
          if (!drawMode) {
            const existingHit = raycastExistingBoxes(e.clientX, e.clientY);
            if (existingHit) {
              e.stopPropagation();
              e.preventDefault();
              startEditingBox(existingHit);
              return;
            }
          }
          return; // empty space — let OrbitControls orbit
        }
        e.stopPropagation();
        e.preventDefault();
        // Box click always translates — resize is only via face arrows
        const ground = screenToGround(e.clientX, e.clientY, el);
        if (!ground) return;
        moveStartGround = ground.clone();
        moveStartCenter = [...previewCenter];
        drawPhase = "moving";
      }
    };

    const onPointerMove = (e: PointerEvent) => {
      if (drawPhase === "drawing-base") {
        e.stopPropagation();
        const hit = screenToGround(e.clientX, e.clientY, el);
        if (hit) { baseCornerB = hit.clone(); updatePreviewFootprint(); }
      } else if (drawPhase === "drawing-height") {
        e.stopPropagation();
        boxHeight = computeBoxHeight(e.clientY);
        updatePreviewHeight();
      } else if (drawPhase === "rotating") {
        e.stopPropagation();
        const angle = computeRingAngle(e.clientX, e.clientY, rotAxis);
        if (angle === null) return;
        const delta = angle - rotStartAngle;
        _rotDeltaQ.setFromAxisAngle(_AXIS_UNIT_VECS[rotAxis], delta);
        previewQuaternion = new THREE.Quaternion().multiplyQuaternions(_rotDeltaQ, rotStartQuaternion);
      } else if (drawPhase === "moving") {
        e.stopPropagation();
        const hit = screenToGround(e.clientX, e.clientY, el);
        if (hit && moveStartGround) {
          const dx = hit.x - moveStartGround.x;
          const dz = hit.z - moveStartGround.z;
          previewCenter = [moveStartCenter[0] + dx, previewCenter[1], moveStartCenter[2] + dz];
        }
      } else if (drawPhase === "resizing-face") {
        e.stopPropagation();
        // Project the mouse ray onto the best-visible plane that contains the face
        // normal. The plane normal is the component of the camera-forward direction
        // that is perpendicular to the drag axis — this maximises drag sensitivity
        // regardless of how the box is rotated.
        const C = _resizeWorldDir;
        camera.current.getWorldDirection(_resizeF);
        _resizePlaneNormal.copy(_resizeF).addScaledVector(C, -_resizeF.dot(C));
        if (_resizePlaneNormal.lengthSq() < 1e-6) {
          // Camera nearly parallel to face normal — use world Y (or X for vertical arrows)
          _resizePlaneNormal.set(Math.abs(C.y) > 0.99 ? 1 : 0, Math.abs(C.y) > 0.99 ? 0 : 1, 0);
        }
        _resizePlaneNormal.normalize();
        _resizeDragPlane.setFromNormalAndCoplanarPoint(_resizePlaneNormal, _resizeStartFaceCenter);
        setupRay(e.clientX, e.clientY);
        if (!_raycastRay.ray.intersectPlane(_resizeDragPlane, _resizeHitPt)) return;
        // Signed displacement along the face normal (positive = extruding outward)
        const drag = _resizeHitPt.sub(_resizeStartFaceCenter).dot(C);
        const newSize = [...resizeStartSize] as [number, number, number];
        const newCenter = [...resizeStartCenter] as [number, number, number];
        newSize[resizeAxis] = Math.max(MIN_GEOMETRY_SIZE, resizeStartSize[resizeAxis] + drag);
        newCenter[0] = resizeStartCenter[0] + C.x * drag / 2;
        newCenter[1] = resizeStartCenter[1] + C.y * drag / 2;
        newCenter[2] = resizeStartCenter[2] + C.z * drag / 2;
        previewSize = newSize;
        previewCenter = newCenter;
      } else if (drawPhase === "confirming") {
        if (raycastRings(e.clientX, e.clientY)) {
          el.style.cursor = "grab";
        } else {
          const ah = raycastArrows(e.clientX, e.clientY);
          if (ah) {
            el.style.cursor = ah.axis === 1 ? "ns-resize" : ah.axis === 0 ? "ew-resize" : "nesw-resize";
          } else {
            el.style.cursor = raycastBox(e.clientX, e.clientY) ? "grab" : drawMode ? "crosshair" : "default";
          }
        }
      } else {
        el.style.cursor = drawMode ? "crosshair" : "default";
      }
    };

    const onPointerUp = (e: PointerEvent) => {
      if (e.button !== 0) return;
      // No el.contains guard — drag operations must commit even when the pointer is
      // released outside the canvas. drawPhase is the only gate needed because only
      // onPointerDown (which does guard with el.contains) can enter an active phase.
      if (drawPhase === "drawing-base") {
        const footprint = Math.hypot(
          (baseCornerB?.x ?? 0) - (baseCornerA?.x ?? 0),
          (baseCornerB?.z ?? 0) - (baseCornerA?.z ?? 0),
        );
        if (footprint < MIN_FOOTPRINT_SIZE) { resetDraw(); return; }
        heightDragStartScreenY = e.clientY;
        drawPhase = "drawing-height";
      } else if (drawPhase === "rotating") {
        drawPhase = "confirming";
        fireReadyToConfirm();
      } else if (drawPhase === "moving") {
        drawPhase = "confirming";
        fireReadyToConfirm();
      } else if (drawPhase === "resizing-face") {
        drawPhase = "confirming";
        fireReadyToConfirm();
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

  // Cancel in-flight draw or edit when the mode toggles in either direction.
  // The early return before reading drawPhase is intentional: it prevents
  // drawPhase from becoming a reactive dependency, avoiding an immediate
  // resetDraw() when drawPhase transitions out of idle during a draw.
  let _prevDrawMode = false;
  $effect(() => {
    const mode = drawMode;
    if (mode === _prevDrawMode) return;
    _prevDrawMode = mode;
    if (drawPhase !== "idle") resetDraw();
  });

  // React to parent requesting a reset (Cancel button in DOM overlay)
  let prevExternalReset = 0;
  $effect(() => {
    if (externalReset > prevExternalReset) {
      prevExternalReset = externalReset;
      resetDraw();
    }
  });

  // ─── Draw helpers ─────────────────────────────────────────────────────────────

  function screenToGround(
    clientX: number,
    clientY: number,
    domEl: HTMLElement,
    y = floorY,
  ): THREE.Vector3 | null {
    const rect = domEl.getBoundingClientRect();
    _screenNdc.set(
      ((clientX - rect.left) / rect.width) * 2 - 1,
      -((clientY - rect.top) / rect.height) * 2 + 1,
    );
    _screenRay.setFromCamera(_screenNdc, camera.current);
    _groundPlane.constant = -y;
    return _screenRay.ray.intersectPlane(_groundPlane, _screenGroundHit) ? _screenGroundHit : null;
  }

  function computeBoxHeight(currentScreenY: number): number {
    const dy = heightDragStartScreenY - currentScreenY;
    const footprintDiag = Math.hypot(
      (baseCornerB?.x ?? 0) - (baseCornerA?.x ?? 0),
      (baseCornerB?.z ?? 0) - (baseCornerA?.z ?? 0),
    );
    return Math.max(footprintDiag * HEIGHT_MINIMUM_FROM_FOOTPRINT_RATIO, dy * footprintDiag * HEIGHT_DRAG_SCALE_PER_PX);
  }

  function updatePreviewFootprint(): void {
    if (!baseCornerA || !baseCornerB) return;
    const sx = Math.abs(baseCornerB.x - baseCornerA.x);
    const sz = Math.abs(baseCornerB.z - baseCornerA.z);
    const cx = (baseCornerA.x + baseCornerB.x) / 2;
    const cz = (baseCornerA.z + baseCornerB.z) / 2;
    previewCenter = [cx, floorY + boxHeight / 2, cz];
    previewSize = [Math.max(MIN_GEOMETRY_SIZE, sx), Math.max(MIN_GEOMETRY_SIZE, boxHeight), Math.max(MIN_GEOMETRY_SIZE, sz)];
  }

  function updatePreviewHeight(): void {
    previewCenter = [previewCenter[0], floorY + boxHeight / 2, previewCenter[2]];
    previewSize = [previewSize[0], Math.max(MIN_GEOMETRY_SIZE, boxHeight), previewSize[2]];
  }

  function resetDraw(): void {
    drawPhase = "idle";
    previewVisible = false;
    baseCornerA = null;
    baseCornerB = null;
    boxHeight = 0;
    moveStartGround = null;
    previewQuaternion = new THREE.Quaternion();
    editingBoxId = null;
    onDrawCanceled?.();
  }

  function startEditingBox(bbox: LocalBBox3D): void {
    const t = bboxTransform(bbox);
    previewCenter = t.position;
    previewSize = t.size;
    previewQuaternion = t.quaternion.clone();
    previewVisible = true;
    boxHeight = t.size[1];
    editingBoxId = bbox.id;
    drawPhase = "confirming";
    onReadyToConfirm?.(
      threeBoxToLanceXYZWHD(t.position, t.size),
      threeQuaternionToLanceRotation(t.quaternion),
      bbox.id,
    );
  }

  function fireReadyToConfirm(): void {
    onReadyToConfirm?.(
      threeBoxToLanceXYZWHD(previewCenter, previewSize),
      threeQuaternionToLanceRotation(previewQuaternion),
      editingBoxId ?? undefined,
    );
  }

  // ─── Keyboard shortcuts ───────────────────────────────────────────────────────

  onMount(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null;
      if (
        target &&
        (target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.isContentEditable)
      )
        return;

      if (e.key === "Escape") {
        e.preventDefault();
        resetDraw();
      } else if (e.key === "Enter") {
        if (drawPhase === "drawing-height") {
          e.preventDefault();
          if (boxHeight < MIN_BOX_HEIGHT) { resetDraw(); return; }
          fireReadyToConfirm();
          drawPhase = "confirming";
        }
      }
    };

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  });

  // ─── Point cloud loading ─────────────────────────────────────────────────────

  onMount(() => {
    if (!pointCloudUrl) {
      loading = false;
      return;
    }

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS);

    void (async () => {
      try {
        const response = await fetch(pointCloudUrl, { signal: controller.signal });
        const buffer = await response.arrayBuffer();

      const { positions: pos, colors: col, bounds } = parsePointCloud(buffer);

      floorY = bounds.minY;

      const center: [number, number, number] = [
        (bounds.minX + bounds.maxX) / 2,
        (bounds.minY + bounds.maxY) / 2,
        (bounds.minZ + bounds.maxZ) / 2,
      ];

      const size = Math.max(
        bounds.maxX - bounds.minX,
        bounds.maxY - bounds.minY,
        bounds.maxZ - bounds.minZ,
      );
      const distance = size * CAMERA_DISTANCE_FACTOR;

      const newPos: [number, number, number] = [
        center[0] + distance,
        center[1] + distance * CAMERA_HEIGHT_FACTOR,
        center[2] + distance,
      ];
      cameraTarget = center;
      cameraPosition = newPos;

      // Directly sync OrbitControls since we removed the reactive target prop.
      // The <T.PerspectiveCamera position={cameraPosition}> effect is async, so
      // we also set the camera position directly so update() uses the right value.
      if (controlsRef) {
        const cam = controlsRef.object as THREE.PerspectiveCamera;
        cam.position.set(newPos[0], newPos[1], newPos[2]);
        cam.lookAt(center[0], center[1], center[2]);
        controlsRef.target.set(center[0], center[1], center[2]);
        controlsRef.update();
      }

      positions = pos;
      colors = col;
      } catch (e) {
        if (e instanceof DOMException && e.name === "AbortError") {
          onLoadError?.("Point cloud load timed out");
        } else {
          onLoadError?.(e instanceof Error ? e.message : "Failed to load point cloud");
        }
      } finally {
        clearTimeout(timeoutId);
        loading = false;
      }
    })();

    return () => {
      clearTimeout(timeoutId);
      controller.abort();
    };
  });

  const LABEL_OFFSET = 0.3;
  let boxRenders = $derived(
    bboxes3d.filter((bbox) => bbox.id !== editingBoxId).map((bbox) => {
      const t = bboxTransform(bbox);
      const labelPos: [number, number, number] = [
        t.position[0],
        t.position[1] + t.size[1] / 2 + LABEL_OFFSET,
        t.position[2],
      ];
      // BoxGeometry is created here (stable per bboxes3d change) and disposed in the
      // template's oncreate once EdgesGeometry has consumed it in its constructor.
      const boxGeometry = new THREE.BoxGeometry(t.size[0], t.size[1], t.size[2]);
      return {
        id: bbox.id,
        transform: t,
        boxGeometry,
        labelPos,
        label: pickEntityLabel(bbox.entity),
      };
    }),
  );
</script>

<T.PerspectiveCamera
  makeDefault
  position={cameraPosition}
  oncreate={(ref) => {
    ref.lookAt(...cameraTarget);
  }}
>
  <OrbitControls
    enableDamping={cameraMode === "orbit"}
    dampingFactor={ORBIT_DAMPING_FACTOR}
    oncreate={(ref) => {
      ref.target.set(cameraTarget[0], cameraTarget[1], cameraTarget[2]);
      controlsRef = ref;
    }}
  />
</T.PerspectiveCamera>

<T.AmbientLight intensity={AMBIENT_LIGHT_INTENSITY} />

{#if !loading && positions.length > 0}
  <T.Points>
    <T.BufferGeometry
      oncreate={(ref) => {
        ref.setAttribute("position", new THREE.BufferAttribute(positions, 3));
        ref.setAttribute("color", new THREE.BufferAttribute(colors, 3));
      }}
    />
    <T.PointsMaterial size={POINT_RENDER_SIZE} vertexColors sizeAttenuation />
  </T.Points>
{/if}

{#each boxRenders as render (render.id)}
  <T.LineSegments
    position={render.transform.position}
    quaternion={[
      render.transform.quaternion.x,
      render.transform.quaternion.y,
      render.transform.quaternion.z,
      render.transform.quaternion.w,
    ]}
  >
    <T.EdgesGeometry
      args={[render.boxGeometry]}
      oncreate={() => render.boxGeometry.dispose()}
    />
    <T.LineBasicMaterial color={BOX_COLOR_PERSISTED} linewidth={BOX_LINE_WIDTH} />
  </T.LineSegments>

  {#if render.label}
    <HTML position={render.labelPos} center pointerEvents="none">
      <div
        class="pointer-events-none -translate-y-1 whitespace-nowrap rounded-sm bg-cyan-400/90 px-1.5 py-0.5 text-[10px] font-medium text-black shadow-sm"
      >
        {render.label}
      </div>
    </HTML>
  {/if}
{/each}

<!-- Draft preview box (amber while drawing / adjusting) -->
{#if previewVisible && previewEdgesGeometry}
  <T.LineSegments
    position={previewCenter}
    quaternion={[previewQuaternion.x, previewQuaternion.y, previewQuaternion.z, previewQuaternion.w]}
    geometry={previewEdgesGeometry}
  >
    <T.LineBasicMaterial color={BOX_COLOR_PREVIEW} linewidth={BOX_LINE_WIDTH} />
  </T.LineSegments>
{/if}

<!-- Rotation gizmo rings — visible while adjusting (confirming / rotating), toggleable -->
{#if previewVisible && showRings && (drawPhase === "confirming" || drawPhase === "rotating")}
  {#each RING_DEFS as ring}
    <T.Mesh position={previewCenter} rotation={[ring.euler.x, ring.euler.y, ring.euler.z]}>
      <T.TorusGeometry args={[gizmoRingRadius, gizmoTubeRadius, 6, 64]} />
      <T.MeshBasicMaterial color={ring.color} transparent opacity={0.75} />
    </T.Mesh>
  {/each}
{/if}

<!-- Resize arrows — shaft + arrowhead per face, visible while confirming or actively resizing -->
{#if previewVisible && showArrows && (drawPhase === "confirming" || drawPhase === "resizing-face")}
  {#each arrowGizmos as arrow (arrow.id)}
    <T.Group position={arrow.pos} quaternion={arrow.quat}>
      <T.Mesh position={[0, arrowShaftOffsetY, 0]}>
        <T.CylinderGeometry args={[arrowShaftRadius, arrowShaftRadius, arrowShaftLength, 8]} />
        <T.MeshBasicMaterial color={arrow.color} transparent opacity={0.85} />
      </T.Mesh>
      <T.Mesh position={[0, arrowHeadOffsetY, 0]}>
        <T.ConeGeometry args={[arrowRadius, arrowHeadLength, 8]} />
        <T.MeshBasicMaterial color={arrow.color} transparent opacity={0.85} />
      </T.Mesh>
    </T.Group>
  {/each}
{/if}

<!-- Phase hint (non-interactive) -->
{#if activeDragging}
  <HTML position={cameraTarget} center pointerEvents="none">
    <div
      class="pointer-events-none rounded bg-black/60 px-2 py-1 text-[10px] text-white"
      style="transform: translate(-50%, calc(-50% - 60px));"
    >
      {#if drawPhase === "drawing-base"}
        Drag to define footprint
      {:else if drawPhase === "drawing-height"}
        Move mouse to set height · Click or Enter to confirm
      {:else if drawPhase === "moving"}
        Drag to reposition · Release to lock
      {:else if drawPhase === "resizing-face"}
        Drag to resize · Release to lock
      {:else if drawPhase === "rotating"}
        Drag ring to rotate · Release to lock
      {/if}
    </div>
  </HTML>
{/if}

<T.GridHelper args={[GRID_SIZE, GRID_DIVISIONS, GRID_COLOR_CENTER, GRID_COLOR_LINES]} />
