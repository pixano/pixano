<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { T, useThrelte } from "@threlte/core";
  import { OrbitControls } from "@threlte/extras";
  import { onMount } from "svelte";
  import * as THREE from "three";
  import type { OrbitControls as ThreeOrbitControls } from "three/examples/jsm/controls/OrbitControls.js";

  import { PointCloudCamera } from "./usePointCloudCamera.svelte.js";
  // RING_DEFS is the orbit-indicator's ring geometry (camera UI), not annotation logic.
  import { RING_DEFS } from "$lib/annotations/kinds/3d/bbox3d/boxEditorConstants.js";
  import { RENDERER_FACTORIES_3D, TOOLS_3D } from "$lib/annotations/scene/registry3d.js";
  import type { Scene3DContext, SceneContextBase } from "$lib/annotations/scene/sceneContext.js";
  import type { ToolHandle3D } from "$lib/annotations/scene/tool.js";
  import type { PointCloudColorController } from "$lib/pointcloud/pointCloudColorController.svelte.js";
  import { parsePointCloud } from "$lib/pointcloud/pointCloudParser.js";

  interface Props {
    pointCloudUrl?: string;
    /** Agnostic seam from the host widget; the scene completes it into a Scene3DContext. */
    seam: SceneContextBase;
    /** Active tool id from the 3D tool registry. */
    activeToolId?: string;
    cameraMode?: "orbit" | "first-person";
    onLoadError?: (message: string) => void;
    /** Per-tool host props keyed by tool id; forwarded opaquely to each overlay. */
    toolProps?: Record<string, Record<string, unknown>>;
    /**
     * Host-owned colouring. The scene hands it the parsed cloud and renders the
     * buffer it publishes; which mode produced those colours is none of the
     * scene's business.
     */
    colors: PointCloudColorController;
  }

  let {
    pointCloudUrl,
    seam,
    activeToolId = "",
    cameraMode = "orbit",
    onLoadError,
    toolProps = {},
    colors,
  }: Props = $props();

  // ─── Rendering state ──────────────────────────────────────────────────────
  let positions = $state<Float32Array>(new Float32Array(0));
  let loading = $state(true);
  /** The live colour attribute, so a recolour can mark it dirty in place. */
  let colorAttribute: THREE.BufferAttribute | null = null;
  let floorY = $state(0);
  let controlsRef = $state<ThreeOrbitControls | null>(null);
  // Each tool publishes its handle by id; the scene reads the active one (camera
  // drag-lock + which box a renderer must skip). Keyed by id so a second editing
  // tool can't clobber the first — previously a single shared handle (DEBT-6).
  let toolHandles = $state<Record<string, ToolHandle3D | undefined>>({});
  const activeHandle = $derived(toolHandles[activeToolId]);

  /** Components per vertex in the geometry's buffers: XYZ and RGB. */
  const POSITION_COMPONENTS = 3;
  const COLOR_COMPONENTS = 3;

  const AMBIENT_LIGHT_INTENSITY = 0.6;
  const POINT_RENDER_SIZE = 0.05;
  const GRID_SIZE = 100;
  const GRID_DIVISIONS = 50;
  const GRID_COLOR_CENTER = "#333333";
  const GRID_COLOR_LINES = "#222222";
  const FETCH_TIMEOUT_MS = 30_000;

  const { camera, invalidate } = useThrelte();

  // ─── Composables ──────────────────────────────────────────────────────────

  const cam = new PointCloudCamera(
    () => controlsRef,
    camera,
    () => cameraMode,
    () => activeHandle?.activeDragging ?? false,
  );

  // The scene finishes the agnostic seam into a full Scene3DContext, adding the
  // engine handles only it owns (camera, controls, floor, orbit pivot). Tools
  // and renderers read this; the scene itself names no annotation kind.
  // svelte-ignore state_referenced_locally
  const ctx: Scene3DContext = {
    ...seam,
    get editingId() {
      return activeHandle?.editingId ?? null;
    },
    camera,
    getControls: () => controlsRef,
    get floorY() {
      return floorY;
    },
    get cameraTarget() {
      return cam.cameraTarget;
    },
    get orbitCenterDist() {
      return cam.orbitCenterDist;
    },
    get activeToolId() {
      return activeToolId;
    },
  };

  // ─── Point cloud loading ──────────────────────────────────────────────────
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
        const parsed = parsePointCloud(buffer);

        floorY = parsed.bounds.minY;
        cam.focusOnBounds(parsed.bounds);
        positions = parsed.positions;
        // Hands over the cloud *and* triggers the first colouring pass. Awaited
        // so `loading` only clears once there are colours to draw — otherwise
        // the first frame would upload an all-black buffer.
        await colors.setCloud(parsed);
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

  // A recolour writes into the same buffer, so nothing about the attribute
  // changes — only its contents. Reading `revision` (not `colors.colors`, whose
  // identity is stable) is what makes this run, and `needsUpdate` is what gets
  // the new bytes to the GPU. Threlte's on-demand loop then redraws because this
  // effect invalidated.
  $effect(() => {
    const revision = colors.revision;
    if (!colorAttribute || revision === 0) return;
    colorAttribute.needsUpdate = true;
    invalidate();
  });
</script>

<T.PerspectiveCamera
  makeDefault
  position={cam.cameraPosition}
  oncreate={(ref) => {
    ref.lookAt(...cam.cameraTarget);
  }}
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
        ref.setAttribute("position", new THREE.BufferAttribute(positions, POSITION_COMPONENTS));
        colorAttribute = new THREE.BufferAttribute(colors.colors, COLOR_COMPONENTS);
        ref.setAttribute("color", colorAttribute);
      }}
    />
    <T.PointsMaterial size={POINT_RENDER_SIZE} vertexColors sizeAttenuation />
  </T.Points>
{/if}

<!-- Registered 3D renderers — one component per annotation kind, each pulling
     its kind from the shared collection via ctx. The scene names no kind. -->
{#each RENDERER_FACTORIES_3D as factory (factory.kind)}
  {@const Renderer = factory.component}
  <Renderer {ctx} />
{/each}

<!-- Active tool overlays — each tool owns its interactive editor + transient
     preview. The scene forwards ctx + opaque per-tool host props and binds the
     tool's handle (drag-lock + edited-box id). The scene names no kind. -->
{#each TOOLS_3D as tool (tool.id)}
  {#if tool.overlay}
    {@const Overlay = tool.overlay}
    <Overlay {ctx} {...toolProps[tool.id] ?? {}} reportHandle={(h) => (toolHandles[tool.id] = h)} />
  {/if}
{/each}

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
      <T.MeshBasicMaterial
        color="#ffffff"
        transparent
        opacity={0.5}
        depthTest={false}
        depthWrite={false}
      />
    </T.Mesh>
  {/each}
{/if}
