<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import Konva from "konva";
  import { Circle, Group, Shape as KonvaShape } from "svelte-konva";

  import { SaveShapeType, type Reference, type Shape } from "@pixano/core";

  import { sceneFunc } from "../api/maskApi";
  import { INPUTRECT_STROKEWIDTH } from "../lib/constants";
  import type { PolygonGroupPoint } from "../lib/types/canvas2dTypes";
  import PolygonPoints from "./PolygonPoints.svelte";

  // Exports
  export let viewRef: Reference;
  export let newShape: Shape;
  export let stage: Konva.Stage;
  export let zoomFactor: Record<string, number>;
  const POLYGON_ID = "creating";

  // Distance threshold (in screen pixels) for snapping to an edge
  const EDGE_SNAP_PX = 8;

  let polygonPoints: PolygonGroupPoint[][] = [];
  let hoveredEdge: { x: number; y: number; shapeIndex: number; afterIndex: number } | null = null;

  $: {
    if (newShape.status === "creating" && newShape.type === SaveShapeType.mask) {
      const closedPolygons = newShape.closedPolygons || [];
      const currentPoints = newShape.points || [];

      if (newShape.phase === "editing") {
        polygonPoints = closedPolygons;
      } else {
        // Drawing phase: show closed polygons + in-progress polygon
        const lastPolygonDetailsPoint = currentPoints.at(-1);
        const existingInProgress =
          polygonPoints.length > closedPolygons.length
            ? polygonPoints[polygonPoints.length - 1]
            : [];
        const lastSimplifiedPoint = existingInProgress.at(-1);

        if (lastPolygonDetailsPoint && lastPolygonDetailsPoint?.id !== lastSimplifiedPoint?.id) {
          const updatedInProgress = [...existingInProgress, lastPolygonDetailsPoint];
          polygonPoints = [...closedPolygons, updatedInProgress];
        } else if (currentPoints.length === 0) {
          polygonPoints = closedPolygons;
        }
      }
    }
    if (newShape.status === "none") {
      polygonPoints = [];
      hoveredEdge = null;
    }
  }

  function handlePolygonPointsClick(pointIndex: number, shapeIndex: number) {
    if (newShape.status !== "creating" || newShape.type !== SaveShapeType.mask) return;

    // Only close on click of point 0 of the in-progress (last) polygon during drawing
    if (
      newShape.phase === "drawing" &&
      pointIndex === 0 &&
      shapeIndex === polygonPoints.length - 1 &&
      polygonPoints[shapeIndex]?.length >= 3
    ) {
      const closedPoly = polygonPoints[shapeIndex];
      newShape = {
        ...newShape,
        closedPolygons: [...newShape.closedPolygons, closedPoly],
        points: [],
        phase: "editing",
      };
    }
  }

  function handlePolygonPointsDragMove(id: number, i: number) {
    const pos = stage.findOne(`#dot-${POLYGON_ID}-${i}-${id}`).position();
    const newPolygonPoints = polygonPoints.map((points, pi) =>
      pi === i
        ? points.map((point) => (point.id === id ? { ...point, x: pos.x, y: pos.y } : point))
        : points,
    );
    polygonPoints = newPolygonPoints;

    // Sync back to newShape.closedPolygons when editing
    if (
      newShape.status === "creating" &&
      newShape.type === SaveShapeType.mask &&
      newShape.phase === "editing"
    ) {
      newShape = { ...newShape, closedPolygons: newPolygonPoints };
    }
  }

  // Project point p onto segment a→b, return distance and projected point
  function projectOnSegment(
    p: { x: number; y: number },
    a: { x: number; y: number },
    b: { x: number; y: number },
  ) {
    const dx = b.x - a.x;
    const dy = b.y - a.y;
    const len2 = dx * dx + dy * dy;
    if (len2 === 0) return { dist: Math.hypot(p.x - a.x, p.y - a.y), point: a };
    let t = ((p.x - a.x) * dx + (p.y - a.y) * dy) / len2;
    t = Math.max(0, Math.min(1, t));
    const proj = { x: a.x + t * dx, y: a.y + t * dy };
    return { dist: Math.hypot(p.x - proj.x, p.y - proj.y), point: proj };
  }

  function findClosestEdge(pos: { x: number; y: number }, polys: PolygonGroupPoint[][]) {
    let bestDist = Infinity;
    let bestShape = -1;
    let bestIdx = -1;
    let bestPoint = pos;

    for (let si = 0; si < polys.length; si++) {
      const poly = polys[si];
      for (let pi = 0; pi < poly.length; pi++) {
        const p1 = poly[pi];
        const p2 = poly[(pi + 1) % poly.length];
        const { dist, point } = projectOnSegment(pos, p1, p2);
        if (dist < bestDist) {
          bestDist = dist;
          bestShape = si;
          bestIdx = pi;
          bestPoint = point;
        }
      }
    }
    return { bestDist, bestShape, bestIdx, bestPoint };
  }

  function handleShapeMouseMove() {
    if (
      newShape.status !== "creating" ||
      newShape.type !== SaveShapeType.mask ||
      newShape.phase !== "editing"
    ) {
      hoveredEdge = null;
      return;
    }

    const pos = stage.findOne(`#${viewRef.name}`)?.getRelativePointerPosition();
    if (!pos) {
      hoveredEdge = null;
      return;
    }

    const threshold = EDGE_SNAP_PX / zoomFactor[viewRef.name];
    const { bestDist, bestShape, bestIdx, bestPoint } = findClosestEdge(
      pos,
      newShape.closedPolygons,
    );

    if (bestDist < threshold && bestShape >= 0) {
      hoveredEdge = {
        x: bestPoint.x,
        y: bestPoint.y,
        shapeIndex: bestShape,
        afterIndex: bestIdx,
      };
    } else {
      hoveredEdge = null;
    }
  }

  function handleShapeMouseLeave() {
    hoveredEdge = null;
  }

  function handleEdgeClick(e: CustomEvent) {
    if (
      newShape.status !== "creating" ||
      newShape.type !== SaveShapeType.mask ||
      newShape.phase !== "editing"
    )
      return;

    const konvaEvt = e.detail as Konva.KonvaEventObject<MouseEvent>;
    const pos = stage.findOne(`#${viewRef.name}`)?.getRelativePointerPosition();
    if (!pos) return;

    konvaEvt.cancelBubble = true; // always stop propagation in editing phase

    if (hoveredEdge) {
      // Near an edge — insert vertex
      const shape = newShape.closedPolygons[hoveredEdge.shapeIndex];
      const newPoint: PolygonGroupPoint = {
        x: Math.round(hoveredEdge.x),
        y: Math.round(hoveredEdge.y),
        id: Math.max(...shape.map((p) => p.id)) + 1,
      };
      const updated = [...newShape.closedPolygons];
      const updatedPoly = [...shape];
      updatedPoly.splice(hoveredEdge.afterIndex + 1, 0, newPoint);
      updated[hoveredEdge.shapeIndex] = updatedPoly;
      newShape = { ...newShape, closedPolygons: updated };
      polygonPoints = updated;
      hoveredEdge = null;
    } else {
      // Not near an edge — start new polygon at click position
      newShape = {
        ...newShape,
        phase: "drawing",
        points: [{ x: Math.round(pos.x), y: Math.round(pos.y), id: 0 }],
      };
    }
  }

  // Polygon arrays for custom sceneFunc rendering
  $: closedPolygons =
    newShape.status === "creating" && newShape.type === SaveShapeType.mask
      ? newShape.closedPolygons
      : [];

  $: inProgressPoints = (() => {
    if (
      newShape.status === "creating" &&
      newShape.type === SaveShapeType.mask &&
      newShape.phase === "drawing" &&
      polygonPoints.length > (newShape.closedPolygons?.length || 0)
    ) {
      return polygonPoints[polygonPoints.length - 1] || [];
    }
    return [];
  })();

  function drawPolygonScene(ctx: Konva.Context, shape: Konva.Shape) {
    ctx.beginPath();
    for (const poly of closedPolygons) {
      if (poly.length < 2) continue;
      ctx.moveTo(poly[0].x, poly[0].y);
      for (let i = 1; i < poly.length; i++) ctx.lineTo(poly[i].x, poly[i].y);
      ctx.closePath();
    }
    if (inProgressPoints.length > 0) {
      ctx.moveTo(inProgressPoints[0].x, inProgressPoints[0].y);
      for (let i = 1; i < inProgressPoints.length; i++)
        ctx.lineTo(inProgressPoints[i].x, inProgressPoints[i].y);
    }
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const rawCtx = (ctx as any)._context as CanvasRenderingContext2D;
    const fillColor = shape.fill() as string;
    if (fillColor) {
      rawCtx.fillStyle = fillColor;
      rawCtx.fill("evenodd");
    }
    ctx.strokeShape(shape);
  }

  function drawPolygonHit(ctx: Konva.Context, shape: Konva.Shape) {
    // Only capture clicks during editing phase (edge insertion, start new polygon).
    // During drawing, let clicks pass through to the Image node for point addition.
    if (newShape.status !== "creating" || newShape.type !== SaveShapeType.mask || newShape.phase !== "editing") {
      return;
    }
    ctx.beginPath();
    for (const poly of closedPolygons) {
      if (poly.length < 2) continue;
      ctx.moveTo(poly[0].x, poly[0].y);
      for (let i = 1; i < poly.length; i++) ctx.lineTo(poly[i].x, poly[i].y);
      ctx.closePath();
    }
    ctx.fillStrokeShape(shape);
  }
</script>

{#if newShape.status === "creating" && newShape.type === SaveShapeType.mask && newShape.viewRef.name === viewRef.name}
  <Group config={{ id: "polygon", draggable: true }}>
    <!-- All polygons rendered with even-odd fill for hole support -->
    <KonvaShape
      on:click={handleEdgeClick}
      on:mousemove={handleShapeMouseMove}
      on:mouseleave={handleShapeMouseLeave}
      config={{
        sceneFunc: drawPolygonScene,
        stroke: "hsl(316deg 60% 29.41%)",
        strokeWidth: INPUTRECT_STROKEWIDTH / zoomFactor[viewRef.name],
        fill: "#f9f4f773",
        hitFunc: drawPolygonHit,
      }}
    />
    <PolygonPoints
      {viewRef}
      {stage}
      {zoomFactor}
      polygonId={POLYGON_ID}
      points={polygonPoints}
      {handlePolygonPointsClick}
      {handlePolygonPointsDragMove}
      handlePolygonPointsDragEnd={null}
    />
    <!-- Edge hover indicator: shows where a new vertex will be inserted -->
    {#if hoveredEdge}
      <Circle
        config={{
          x: hoveredEdge.x,
          y: hoveredEdge.y,
          radius: 5 / zoomFactor[viewRef.name],
          fill: "#781e60",
          stroke: "white",
          strokeWidth: 1.5 / zoomFactor[viewRef.name],
          listening: false,
        }}
      />
    {/if}
  </Group>
{:else if newShape.status === "saving" && newShape.type === SaveShapeType.mask && newShape.viewRef.name === viewRef.name}
  <Group config={{ id: "polygon" }}>
    <KonvaShape
      config={{
        sceneFunc: (ctx, shape) => sceneFunc(ctx, shape, newShape.masksImageSVG),
        stroke: "hsl(316deg 60% 29.41%)",
        strokeWidth: INPUTRECT_STROKEWIDTH / zoomFactor[viewRef.name],
        fill: "#f9f4f773",
      }}
    />
  </Group>
{/if}
