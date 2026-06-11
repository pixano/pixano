/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import * as THREE from "three";
import type { OrbitControls as ThreeOrbitControls } from "three/examples/jsm/controls/OrbitControls.js";

export interface PointCloudBounds {
  minX: number; maxX: number;
  minY: number; maxY: number;
  minZ: number; maxZ: number;
}

export class PointCloudCamera {
  cameraPosition = $state<[number, number, number]>([30, 20, 30]);
  cameraTarget = $state<[number, number, number]>([0, 0, 0]);
  orbitCenterDist = $state(Math.hypot(30, 20, 30));

  readonly ORBIT_INDICATOR_FRACTION = 0.05;
  orbitIndicatorRadius = $derived(this.orbitCenterDist * this.ORBIT_INDICATOR_FRACTION);

  readonly ORBIT_DAMPING_FACTOR = 0.07;

  private readonly CAMERA_DISTANCE_FACTOR = 1.2;
  private readonly CAMERA_HEIGHT_FACTOR = 0.5;
  private readonly WHEEL_LINE_HEIGHT_PX = 40;

  // First-person scratch — hoisted to avoid per-event allocations
  private readonly _worldUp = new THREE.Vector3(0, 1, 0);
  private readonly _localRight = new THREE.Vector3(1, 0, 0);
  private readonly _forward = new THREE.Vector3();
  private readonly _flyDir = new THREE.Vector3();

  constructor(
    private readonly getControlsRef: () => ThreeOrbitControls | null,
    private readonly camera: { current: THREE.PerspectiveCamera },
    private readonly getCameraMode: () => "orbit" | "first-person",
    private readonly getActiveDragging: () => boolean,
  ) {
    // Lock / unlock OrbitControls while the user is dragging a gizmo
    $effect(() => {
      const ref = this.getControlsRef();
      if (!ref) return;
      const activeDragging = this.getActiveDragging();
      const cameraMode = this.getCameraMode();

      if (cameraMode === "orbit") {
        ref.enableRotate = !activeDragging;
        ref.enableZoom = !activeDragging;
        ref.enablePan = !activeDragging;
        ref.screenSpacePanning = true;
        ref.mouseButtons = activeDragging
          ? { LEFT: null, MIDDLE: null, RIGHT: null }
          : { LEFT: THREE.MOUSE.ROTATE, MIDDLE: THREE.MOUSE.DOLLY, RIGHT: THREE.MOUSE.PAN };
      } else {
        ref.enableRotate = false;
        ref.enableZoom = false;
        ref.enablePan = !activeDragging;
        ref.screenSpacePanning = false;
        ref.mouseButtons = activeDragging
          ? { LEFT: null, MIDDLE: null, RIGHT: null }
          : { LEFT: THREE.MOUSE.PAN, MIDDLE: null, RIGHT: null };
      }
    });

    // Orbit mode: keep cameraTarget and orbitCenterDist in sync with OrbitControls
    $effect(() => {
      const ref = this.getControlsRef();
      if (!ref || this.getCameraMode() !== "orbit") return;

      this.orbitCenterDist = this.camera.current.position.distanceTo(ref.target);

      const onChange = () => {
        this.cameraTarget = [ref.target.x, ref.target.y, ref.target.z];
        this.orbitCenterDist = this.camera.current.position.distanceTo(ref.target);
      };
      ref.addEventListener("change", onChange);
      return () => ref.removeEventListener("change", onChange);
    });

    // First-person mode: right-drag = look-around, scroll = fly-through
    $effect(() => {
      const ref = this.getControlsRef();
      if (!ref || this.getCameraMode() !== "first-person") return;

      const ROTATION_SENSITIVITY = 0.003;
      const FLY_SPEED = 0.05;
      let isRightDragging = false;
      let lastX = 0;
      let lastY = 0;

      const onContextMenu = (e: MouseEvent) => e.preventDefault();

      const onPointerDown = (e: PointerEvent) => {
        if (e.button !== 2 || this.getActiveDragging()) return;
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
        cam.rotateOnWorldAxis(this._worldUp, -dx * ROTATION_SENSITIVITY);
        cam.rotateOnAxis(this._localRight, -dy * ROTATION_SENSITIVITY);
        const dist = cam.position.distanceTo(ref.target);
        this._forward.set(0, 0, -1).applyQuaternion(cam.quaternion);
        ref.target.copy(cam.position).addScaledVector(this._forward, dist);
        this.cameraTarget = [ref.target.x, ref.target.y, ref.target.z];
        ref.update();
      };

      const onPointerUp = (e: PointerEvent) => { if (e.button === 2) isRightDragging = false; };

      const onChange = () => { this.cameraTarget = [ref.target.x, ref.target.y, ref.target.z]; };
      ref.addEventListener("change", onChange);

      const onWheel = (e: WheelEvent) => {
        e.preventDefault();
        const cam = ref.object as THREE.PerspectiveCamera;
        cam.getWorldDirection(this._flyDir);
        const delta = e.deltaMode === 1 ? e.deltaY * this.WHEEL_LINE_HEIGHT_PX : e.deltaY;
        cam.position.addScaledVector(this._flyDir, -delta * FLY_SPEED);
        ref.target.addScaledVector(this._flyDir, -delta * FLY_SPEED);
        this.cameraTarget = [ref.target.x, ref.target.y, ref.target.z];
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
  }

  /** Position the camera to frame the given point cloud bounds and sync OrbitControls immediately. */
  focusOnBounds(bounds: PointCloudBounds): void {
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
    const distance = size * this.CAMERA_DISTANCE_FACTOR;
    const newPos: [number, number, number] = [
      center[0] + distance,
      center[1] + distance * this.CAMERA_HEIGHT_FACTOR,
      center[2] + distance,
    ];
    this.cameraTarget = center;
    this.cameraPosition = newPos;

    const ref = this.getControlsRef();
    if (ref) {
      const cam = ref.object as THREE.PerspectiveCamera;
      cam.position.set(newPos[0], newPos[1], newPos[2]);
      cam.lookAt(center[0], center[1], center[2]);
      ref.target.set(center[0], center[1], center[2]);
      ref.update();
    }
  }
}
