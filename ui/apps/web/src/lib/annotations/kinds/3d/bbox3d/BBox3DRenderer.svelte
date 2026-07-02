<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { T } from "@threlte/core";
  import { HTML } from "@threlte/extras";
  import * as THREE from "three";

  import { bboxTransform } from "$lib/annotations/coordinateTransforms";
  import type { Scene3DContext } from "$lib/annotations/scene/sceneContext.js";
  import { pickEntityLabel } from "$lib/annotations/types";

  interface Props {
    ctx: Scene3DContext;
  }

  let { ctx }: Props = $props();

  const BOX_COLOR_PERSISTED = "#22d3ee";
  const BOX_LINE_WIDTH = 2;
  const LABEL_OFFSET = 0.3;

  // One shared unit-cube wireframe; every box reuses it, scaled to its size. The
  // render path therefore allocates no geometry per box (CODING_STANDARDS: never
  // allocate in render/loop paths — previously a THREE.BoxGeometry per box per
  // reactive tick). Immutable and app-lifetime, so it is never disposed.
  const UNIT_BOX_EDGES = new THREE.EdgesGeometry(new THREE.BoxGeometry(1, 1, 1));

  // Pull the kind straight from the shared collection; skip the annotation the
  // active editing tool currently owns (it draws its own live preview).
  const renders = $derived(
    ctx.collection
      .byKind("bbox3d")
      .filter((a) => a.id !== ctx.editingId)
      .map((a) => {
        const t = bboxTransform(a.geometry);
        const q = t.quaternion;
        return {
          id: a.id,
          position: t.position,
          quaternionArr: [q.x, q.y, q.z, q.w] as [number, number, number, number],
          size: t.size,
          labelPos: [t.position[0], t.position[1] + t.size[1] / 2 + LABEL_OFFSET, t.position[2]] as [
            number,
            number,
            number,
          ],
          label: pickEntityLabel(a.entity),
        };
      }),
  );
</script>

{#each renders as render (render.id)}
  <T.LineSegments
    position={render.position}
    quaternion={render.quaternionArr}
    scale={render.size}
    geometry={UNIT_BOX_EDGES}
  >
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
