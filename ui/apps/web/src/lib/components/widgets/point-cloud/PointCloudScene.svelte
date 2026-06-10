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

  import { parsePointCloud } from "$lib/annotations/pointCloudParser";
  import { pickEntityLabel } from "$lib/annotations/types";
  import { bboxTransform } from "$lib/annotations/coordinateTransforms";
  import type { LocalBBox3D } from "$lib/api/annotations";
  import type { OrbitControls as ThreeOrbitControls } from "three/examples/jsm/controls/OrbitControls.js";

  import { RING_DEFS } from "./boxEditorConstants.js";
  import { PointCloudCamera } from "./usePointCloudCamera.svelte.js";
  import { BoxEditor } from "./useBoxEditor.svelte.js";
  import type { BBoxRenderData, GizmoVisibility } from "./pointCloudTypes.js";

  interface Props {
    pointCloudUrl?: string;
    bboxes3d?: LocalBBox3D[];
    drawMode?: boolean;
    cameraMode?: "orbit" | "first-person";
    onReadyToConfirm?: (coords: [number, number, number, number, number, number], rotation?: number[], editingId?: string) => void;
    onDrawCanceled?: () => void;
    onLoadError?: (message: string) => void;
    gizmoVisibility?: GizmoVisibility;
  }

  let {
    pointCloudUrl,
    bboxes3d = [],
    drawMode = false,
    cameraMode = "orbit",
    onReadyToConfirm,
    onDrawCanceled,
    onLoadError,
    gizmoVisibility = { rings: true, resizeArrows: true, translateArrows: true },
  }: Props = $props();

  // ─── Rendering state ──────────────────────────────────────────────────────
  let positions = $state<Float32Array>(new Float32Array(0));
  let colors = $state<Float32Array>(new Float32Array(0));
  let loading = $state(true);
  let floorY = $state(0);
  let controlsRef = $state<ThreeOrbitControls | null>(null);

  const AMBIENT_LIGHT_INTENSITY = 0.6;
  const POINT_RENDER_SIZE = 0.05;
  const BOX_LINE_WIDTH = 2;
  const BOX_COLOR_PERSISTED = "#22d3ee";
  const BOX_COLOR_PREVIEW = "#f59e0b";
  const GRID_SIZE = 100;
  const GRID_DIVISIONS = 50;
  const GRID_COLOR_CENTER = "#333333";
  const GRID_COLOR_LINES = "#222222";
  const LABEL_OFFSET = 0.3;
  const FETCH_TIMEOUT_MS = 30_000;

  const { camera } = useThrelte();

  // ─── Composables ──────────────────────────────────────────────────────────

  const cam = new PointCloudCamera(
    () => controlsRef,
    camera,
    () => cameraMode,
    () => editor.activeDragging,
  );

  // Convert LocalBBox3D → BBoxRenderData before passing to the editor so the
  // editor and the scene template stay free of domain format knowledge.
  const bboxesForEditor = $derived<BBoxRenderData[]>(
    bboxes3d.map((bbox) => {
      const t = bboxTransform(bbox);
      return {
        id: bbox.id,
        position: t.position,
        size: t.size,
        quaternion: { x: t.quaternion.x, y: t.quaternion.y, z: t.quaternion.z, w: t.quaternion.w },
        label: pickEntityLabel(bbox.entity),
      };
    }),
  );

  const editor = new BoxEditor(
    camera,
    () => controlsRef,
    () => bboxesForEditor,
    () => drawMode,
    () => floorY,
    () => cam.cameraTarget,
    () => cam.orbitCenterDist,
    () => gizmoVisibility,
    (...args) => onReadyToConfirm?.(...args),
    () => onDrawCanceled?.(),
  );

  /** Exposed so the Widget can reset the FSM via bind:this. */
  export function reset(): void { editor.reset(); }

  // ─── Box renders ──────────────────────────────────────────────────────────
  const boxRenders = $derived(
    bboxesForEditor
      .filter((b) => b.id !== editor.editingBoxId)
      .map((bbox) => {
        const q = bbox.quaternion;
        const boxGeometry = new THREE.BoxGeometry(bbox.size[0], bbox.size[1], bbox.size[2]);
        return {
          id: bbox.id,
          position: bbox.position,
          quaternionArr: [q.x, q.y, q.z, q.w] as [number, number, number, number],
          boxGeometry,
          labelPos: [bbox.position[0], bbox.position[1] + bbox.size[1] / 2 + LABEL_OFFSET, bbox.position[2]] as [number, number, number],
          label: bbox.label,
        };
      }),
  );

  // ─── Point cloud loading ──────────────────────────────────────────────────
  onMount(() => {
    if (!pointCloudUrl) { loading = false; return; }

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS);

    void (async () => {
      try {
        const response = await fetch(pointCloudUrl, { signal: controller.signal });
        const buffer = await response.arrayBuffer();
        const { positions: pos, colors: col, bounds } = parsePointCloud(buffer);

        floorY = bounds.minY;
        cam.focusOnBounds(bounds);
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

    return () => { clearTimeout(timeoutId); controller.abort(); };
  });
</script>

<T.PerspectiveCamera
  makeDefault
  position={cam.cameraPosition}
  oncreate={(ref) => { ref.lookAt(...cam.cameraTarget); }}
>
  <OrbitControls
    enableDamping={cameraMode === "orbit"}
    dampingFactor={cam.ORBIT_DAMPING_FACTOR}
    oncreate={(ref) => {
      ref.target.set(cam.cameraTarget[0], cam.cameraTarget[1], cam.cameraTarget[2]);
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
  <T.LineSegments position={render.position} quaternion={render.quaternionArr}>
    <T.EdgesGeometry
      args={[render.boxGeometry]}
      oncreate={() => render.boxGeometry.dispose()}
    />
    <T.LineBasicMaterial color={BOX_COLOR_PERSISTED} linewidth={BOX_LINE_WIDTH} />
  </T.LineSegments>

  {#if render.label}
    <HTML position={render.labelPos} center pointerEvents="none">
      <div class="pointer-events-none -translate-y-1 whitespace-nowrap rounded-sm bg-cyan-400/90 px-1.5 py-0.5 text-[10px] font-medium text-black shadow-sm">
        {render.label}
      </div>
    </HTML>
  {/if}
{/each}

<!-- Draft preview box -->
{#if editor.previewVisible && editor.previewEdgesGeometry}
  <T.LineSegments
    position={editor.previewCenter}
    quaternion={[editor.previewQuaternion.x, editor.previewQuaternion.y, editor.previewQuaternion.z, editor.previewQuaternion.w]}
    geometry={editor.previewEdgesGeometry}
  >
    <T.LineBasicMaterial color={BOX_COLOR_PREVIEW} linewidth={BOX_LINE_WIDTH} />
  </T.LineSegments>
{/if}

<!-- Rotation gizmo rings -->
{#if editor.previewVisible && gizmoVisibility.rings && (editor.drawPhase === "confirming" || editor.drawPhase === "rotating")}
  {#each editor.ringGizmos as ring, axis (axis)}
    <T.Mesh position={editor.previewCenter} quaternion={ring.quat}>
      <T.TorusGeometry args={[editor.gizmoRingRadius, editor.gizmoTubeRadius, 6, 64]} />
      <T.MeshBasicMaterial color={ring.color} transparent opacity={0.75} />
    </T.Mesh>
  {/each}
{/if}

{#snippet arrowGizmo(arrow: { id: string; pos: [number, number, number]; quat: [number, number, number, number]; color: string })}
  <T.Group position={arrow.pos} quaternion={arrow.quat}>
    <T.Mesh position={[0, editor.arrowShaftOffsetY, 0]}>
      <T.CylinderGeometry args={[editor.arrowShaftRadius, editor.arrowShaftRadius, editor.arrowShaftLength, 8]} />
      <T.MeshBasicMaterial color={arrow.color} transparent opacity={0.85} />
    </T.Mesh>
    <T.Mesh position={[0, editor.arrowHeadOffsetY, 0]}>
      <T.ConeGeometry args={[editor.arrowRadius, editor.arrowHeadLength, 8]} />
      <T.MeshBasicMaterial color={arrow.color} transparent opacity={0.85} />
    </T.Mesh>
  </T.Group>
{/snippet}

<!-- Translation gizmo arrows -->
{#if editor.previewVisible && gizmoVisibility.translateArrows && (editor.drawPhase === "confirming" || (editor.drawPhase === "moving" && editor.moveMode === "axis"))}
  {#each editor.translateArrowGizmos as arrow (arrow.id)}
    {@render arrowGizmo(arrow)}
  {/each}
{/if}

<!-- Resize arrows -->
{#if editor.previewVisible && gizmoVisibility.resizeArrows && (editor.drawPhase === "confirming" || editor.drawPhase === "resizing-face")}
  {#each editor.arrowGizmos as arrow (arrow.id)}
    {@render arrowGizmo(arrow)}
  {/each}
{/if}

<!-- Drag hint -->
{#if editor.activeDragging}
  <HTML position={cam.cameraTarget} center pointerEvents="none">
    <div
      class="pointer-events-none rounded bg-black/60 px-2 py-1 text-[10px] text-white"
      style="transform: translate(-50%, calc(-50% - 60px));"
    >
      {#if editor.drawPhase === "moving"}
        {editor.moveMode === "axis" ? "Drag to translate · Release to lock" : "Drag to reposition · Release to lock"}
      {:else if editor.drawPhase === "resizing-face"}
        Drag to resize · Release to lock
      {:else if editor.drawPhase === "rotating"}
        {["X", "Y", "Z"][editor.rotAxis]}: {editor.rotWorldAngleDeg.toFixed(1)}°
      {/if}
    </div>
  </HTML>
{/if}

<T.GridHelper args={[GRID_SIZE, GRID_DIVISIONS, GRID_COLOR_CENTER, GRID_COLOR_LINES]} />

<!-- Orbit centre indicator — fixed apparent screen size via distance-proportional scale -->
{#if cameraMode === "orbit"}
  {#each RING_DEFS as ring, i (i)}
    <T.Mesh
      position={cam.cameraTarget}
      rotation={[ring.euler.x, ring.euler.y, ring.euler.z]}
      scale={cam.orbitIndicatorRadius}
      renderOrder={999}
    >
      <T.TorusGeometry args={[1, 0.04, 6, 64]} />
      <T.MeshBasicMaterial color="#ffffff" transparent opacity={0.5} depthTest={false} depthWrite={false} />
    </T.Mesh>
  {/each}
{/if}
