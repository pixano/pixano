<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { T } from "@threlte/core";
  import { HTML, OrbitControls } from "@threlte/extras";
  import { onMount } from "svelte";
  import * as THREE from "three";

  import { pickEntityLabel } from "$lib/annotations/types";
  import type { LocalBBox3D } from "$lib/api/annotations";

  interface Props {
    pointCloudUrl?: string;
    bboxes3d?: LocalBBox3D[];
  }

  let { pointCloudUrl, bboxes3d = [] }: Props = $props();

  let positions = $state<Float32Array>(new Float32Array(0));
  let colors = $state<Float32Array>(new Float32Array(0));
  let loading = $state(true);

  let cameraPosition = $state<[number, number, number]>([30, 20, 30]);
  let cameraTarget = $state<[number, number, number]>([0, 0, 0]);

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  let controlsRef = $state<any>(null);

  $effect(() => {
    const ref = controlsRef;
    if (!ref) return;

    const SENSITIVITY = 0.003;
    const FLY_SPEED = 0.05;
    let isRightDragging = false;
    let lastX = 0;
    let lastY = 0;

    const onContextMenu = (e: MouseEvent) => e.preventDefault();

    const onMouseDown = (e: MouseEvent) => {
      if (e.button === 2) {
        isRightDragging = true;
        lastX = e.clientX;
        lastY = e.clientY;
      }
    };

    const onMouseMove = (e: MouseEvent) => {
      if (!isRightDragging) return;
      const dx = e.clientX - lastX;
      const dy = e.clientY - lastY;
      lastX = e.clientX;
      lastY = e.clientY;

      const cam = ref.object as THREE.PerspectiveCamera;
      cam.rotateOnWorldAxis(new THREE.Vector3(0, 1, 0), -dx * SENSITIVITY);
      cam.rotateOnAxis(new THREE.Vector3(1, 0, 0), -dy * SENSITIVITY);

      const dist = cam.position.distanceTo(ref.target);
      const dir = new THREE.Vector3(0, 0, -1).applyQuaternion(cam.quaternion);
      ref.target.copy(cam.position).addScaledVector(dir, dist);
      cameraTarget = [ref.target.x, ref.target.y, ref.target.z];
      ref.update();
    };

    const onMouseUp = (e: MouseEvent) => {
      if (e.button === 2) isRightDragging = false;
    };

    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      const cam = ref.object as THREE.PerspectiveCamera;
      const dir = new THREE.Vector3();
      cam.getWorldDirection(dir);
      const move = dir.multiplyScalar(-e.deltaY * FLY_SPEED);
      cam.position.add(move);
      ref.target.add(move);
      cameraTarget = [ref.target.x, ref.target.y, ref.target.z];
      ref.update();
    };

    ref.domElement.addEventListener("contextmenu", onContextMenu);
    ref.domElement.addEventListener("mousedown", onMouseDown);
    window.addEventListener("mousemove", onMouseMove);
    window.addEventListener("mouseup", onMouseUp);
    ref.domElement.addEventListener("wheel", onWheel, { passive: false });

    return () => {
      ref.domElement.removeEventListener("contextmenu", onContextMenu);
      ref.domElement.removeEventListener("mousedown", onMouseDown);
      window.removeEventListener("mousemove", onMouseMove);
      window.removeEventListener("mouseup", onMouseUp);
      ref.domElement.removeEventListener("wheel", onWheel);
    };
  });

  function lanceToThree(x: number, y: number, z: number): [number, number, number] {
    return [x, z, -y];
  }

  function bboxTransform(bbox: LocalBBox3D): {
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
        size: [sx, sy, sz],
        quaternion: lanceRotationToThree(bbox.rotation),
      };
    }
    return {
      position: lanceToThree(c[0], c[1], c[2]),
      size: [c[3], c[4], c[5]],
      quaternion: lanceRotationToThree(bbox.rotation),
    };
  }

  function lanceRotationToThree(rotation: number[] | undefined): THREE.Quaternion {
    const m = new THREE.Matrix4();
    if (rotation && rotation.length === 9) {
      const r = rotation;
      m.set(r[0], r[1], r[2], 0, r[3], r[4], r[5], 0, r[6], r[7], r[8], 0, 0, 0, 0, 1);
    }
    const S = new THREE.Matrix4().set(1, 0, 0, 0, 0, 0, 1, 0, 0, -1, 0, 0, 0, 0, 0, 1);
    const composed = new THREE.Matrix4().multiplyMatrices(S, m);
    return new THREE.Quaternion().setFromRotationMatrix(composed);
  }

  onMount(async () => {
    if (!pointCloudUrl) {
      loading = false;
      return;
    }
    try {
      const response = await fetch(pointCloudUrl);
      const buffer = await response.arrayBuffer();

      const floats = new Float32Array(buffer);
      const stride = 5;
      const pointCount = Math.floor(floats.length / stride);

      const pos = new Float32Array(pointCount * 3);
      const col = new Float32Array(pointCount * 3);

      let minZ = Infinity,
        maxZ = -Infinity;
      for (let i = 0; i < pointCount; i++) {
        const z = floats[i * stride + 2];
        if (z < minZ) minZ = z;
        if (z > maxZ) maxZ = z;
      }
      const rangeZ = maxZ - minZ || 1;

      for (let i = 0; i < pointCount; i++) {
        const [tx, ty, tz] = lanceToThree(
          floats[i * stride],
          floats[i * stride + 1],
          floats[i * stride + 2],
        );
        pos[i * 3] = tx;
        pos[i * 3 + 1] = ty;
        pos[i * 3 + 2] = tz;

        const t = (floats[i * stride + 2] - minZ) / rangeZ;
        col[i * 3] = t;
        col[i * 3 + 1] = 0.4 + t * 0.4;
        col[i * 3 + 2] = 1 - t * 0.5;
      }

      // ✅ NEW: compute bounding box
      let minX = Infinity,
        minY = Infinity,
        minZp = Infinity;
      let maxX = -Infinity,
        maxY = -Infinity,
        maxZp = -Infinity;

      for (let i = 0; i < pointCount; i++) {
        const x = pos[i * 3];
        const y = pos[i * 3 + 1];
        const z = pos[i * 3 + 2];

        if (x < minX) minX = x;
        if (y < minY) minY = y;
        if (z < minZp) minZp = z;

        if (x > maxX) maxX = x;
        if (y > maxY) maxY = y;
        if (z > maxZp) maxZp = z;
      }

      const center: [number, number, number] = [
        (minX + maxX) / 2,
        (minY + maxY) / 2,
        (minZp + maxZp) / 2,
      ];

      const size = Math.max(maxX - minX, maxY - minY, maxZp - minZp);

      const distance = size * 1.2;

      cameraTarget = center;
      cameraPosition = [center[0] + distance, center[1] + distance * 0.5, center[2] + distance];

      positions = pos;
      colors = col;
    } catch (e) {
      console.error("Failed to load point cloud:", e);
    }
    loading = false;
  });

  const LABEL_OFFSET = 0.3;
  let boxRenders = $derived(
    bboxes3d.map((bbox) => {
      const t = bboxTransform(bbox);
      const labelPos: [number, number, number] = [
        t.position[0],
        t.position[1] + t.size[2] / 2 + LABEL_OFFSET,
        t.position[2],
      ];
      return {
        transform: t,
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
    target={cameraTarget}
    oncreate={(ref) => {
      ref.enableZoom = false;
      ref.enableRotate = false;
      ref.mouseButtons = { LEFT: THREE.MOUSE.PAN, MIDDLE: THREE.MOUSE.DOLLY };
      controlsRef = ref;
    }}
  />
</T.PerspectiveCamera>

<T.AmbientLight intensity={0.6} />

{#if !loading && positions.length > 0}
  <T.Points>
    <T.BufferGeometry
      oncreate={(ref) => {
        ref.setAttribute("position", new THREE.BufferAttribute(positions, 3));
        ref.setAttribute("color", new THREE.BufferAttribute(colors, 3));
      }}
    />
    <T.PointsMaterial size={0.05} vertexColors sizeAttenuation />
  </T.Points>
{/if}

{#each boxRenders as render, i (bboxes3d[i]?.id ?? i)}
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
      args={[
        new THREE.BoxGeometry(
          render.transform.size[0],
          render.transform.size[1],
          render.transform.size[2],
        ),
      ]}
    />
    <T.LineBasicMaterial color="#22d3ee" linewidth={2} />
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

<T.GridHelper args={[100, 50, "#333333", "#222222"]} />
