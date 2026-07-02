<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { T } from "@threlte/core";
  import { HTML } from "@threlte/extras";
  import { onMount } from "svelte";

  import { bboxTransform } from "$lib/annotations/coordinateTransforms";
  import type { Scene3DContext } from "$lib/annotations/scene/sceneContext.js";
  import type { ToolHandle3D } from "$lib/annotations/scene/tool.js";
  import { pickEntityLabel } from "$lib/annotations/types";

  import { BoxEditor } from "./boxEditor.svelte.js";
  import type { BBox3DSession } from "./bbox3dSession.svelte.js";
  import { DRAW_BBOX3D_TOOL_ID, type BBoxRenderData } from "./bbox3dTypes.js";

  interface Props {
    ctx: Scene3DContext;
    /** The bbox3d editing session (gizmo state + confirm/commit), forwarded
     * opaquely by the scene from the host. Optional so the overlay stays
     * assignable to the generic `AnnotationTool3DProps`, but always provided in
     * practice (the tool registers a `createSession`). Owns kind-specific state. */
    session?: BBox3DSession;
    /** Report this tool's handle to the scene (camera lock + renderer skip). */
    reportHandle?: (handle: ToolHandle3D) => void;
  }

  let { ctx, session: maybeSession, reportHandle }: Props = $props();
  // Stable per-widget instance provided by the tool's createSession.
  // svelte-ignore state_referenced_locally
  const session = maybeSession as BBox3DSession;

  const BOX_COLOR_PREVIEW = "#f59e0b";
  const BOX_LINE_WIDTH = 2;

  // This tool only owns interaction while its toolbar entry is selected.
  const drawMode = $derived(ctx.activeToolId === DRAW_BBOX3D_TOOL_ID);

  // Pull bbox3d annotations from the shared collection and convert them to
  // BBoxRenderData for the editor, so the editor stays free of domain formats.
  const bboxesForEditor = $derived<BBoxRenderData[]>(
    ctx.collection.byKind("bbox3d").map((a) => {
      const t = bboxTransform(a.geometry);
      return {
        id: a.id,
        position: t.position,
        size: t.size,
        quaternion: { x: t.quaternion.x, y: t.quaternion.y, z: t.quaternion.z, w: t.quaternion.w },
        label: pickEntityLabel(a.entity),
      };
    }),
  );

  // ctx is a stable object built once by the scene; capturing it here is intended.
  // svelte-ignore state_referenced_locally
  const editor = new BoxEditor(
    ctx.camera,
    () => ctx.getControls(),
    () => bboxesForEditor,
    () => drawMode,
    () => ctx.floorY,
    () => ctx.cameraTarget,
    () => ctx.orbitCenterDist,
    () => session.gizmoVisibility,
    (coords, rotation, editingId) => session.reportReady(coords, rotation, editingId),
    () => session.reportCanceled(),
  );

  // A stable handle whose getters track the editor's reactive state, so the
  // scene's camera (drag lock) and renderers (skip the edited box) react. Reported
  // once on mount (not in an effect, whose dep on the inline reportHandle prop
  // would re-fire on every scene render).
  const handle: ToolHandle3D = {
    get activeDragging() {
      return editor.activeDragging;
    },
    get editingId() {
      return editor.editingBoxId;
    },
  };
  onMount(() => {
    // The session commits then clears the editor; give it the reset hook.
    session.setResetEditor(() => editor.reset());
    reportHandle?.(handle);
  });

  // Precise tuple (CODING_STANDARDS: geometry is tuples, not number[]).
  const previewQuaternionArr = $derived<[number, number, number, number]>([
    editor.previewQuaternion.x,
    editor.previewQuaternion.y,
    editor.previewQuaternion.z,
    editor.previewQuaternion.w,
  ]);
</script>

<!-- Draft preview box -->
{#if editor.previewVisible && editor.previewEdgesGeometry}
  <T.LineSegments
    position={editor.previewCenter}
    quaternion={previewQuaternionArr}
    geometry={editor.previewEdgesGeometry}
  >
    <T.LineBasicMaterial color={BOX_COLOR_PREVIEW} linewidth={BOX_LINE_WIDTH} />
  </T.LineSegments>
{/if}

<!-- Rotation gizmo rings -->
{#if editor.previewVisible && session.gizmoVisibility.rings && (editor.drawPhase === "confirming" || editor.drawPhase === "rotating")}
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
{#if editor.previewVisible && session.gizmoVisibility.translateArrows && (editor.drawPhase === "confirming" || (editor.drawPhase === "moving" && editor.moveMode === "axis"))}
  {#each editor.translateArrowGizmos as arrow (arrow.id)}
    {@render arrowGizmo(arrow)}
  {/each}
{/if}

<!-- Resize arrows -->
{#if editor.previewVisible && session.gizmoVisibility.resizeArrows && (editor.drawPhase === "confirming" || editor.drawPhase === "resizing-face")}
  {#each editor.arrowGizmos as arrow (arrow.id)}
    {@render arrowGizmo(arrow)}
  {/each}
{/if}

<!-- Drag hint -->
{#if editor.activeDragging}
  <HTML position={ctx.cameraTarget} center pointerEvents="none">
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
