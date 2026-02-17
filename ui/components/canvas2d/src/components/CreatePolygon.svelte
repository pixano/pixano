<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import Konva from "konva";
  import { Circle, Group, Shape as KonvaShape } from "svelte-konva";
  import type { ToolEvent } from "@pixano/tools";

  import { sceneFunc } from "../api/maskApi";
  import { INPUTRECT_STROKEWIDTH } from "../lib/constants";
  import {
    CanvasShapeType,
    type CanvasPolygonCreatingShape,
    type CanvasPolygonPoint,
    type CanvasReference,
    type CanvasShape,
  } from "../lib/types/canvasData";
  import PolygonPoints from "./PolygonPoints.svelte";

  export let viewRef: CanvasReference;
  export let newShape: CanvasShape;
  export let stage: Konva.Stage | undefined;
  export let zoomFactor: Record<string, number>;
  export let onToolEvent: (event: ToolEvent) => void = () => {
    return;
  };

  const POLYGON_ID = "creating";
  const EDGE_SNAP_PX = 8;

  const asPolygonCreation = (shape: CanvasShape): CanvasPolygonCreatingShape =>
    shape as CanvasPolygonCreatingShape;
  const getSavedSvg = (shape: CanvasShape): string[] =>
    "masksImageSVG" in shape &&
    Array.isArray(shape.masksImageSVG) &&
    shape.masksImageSVG.every((value) => typeof value === "string")
      ? shape.masksImageSVG
      : [];

  const draftLineColor = "hsl(330, 65%, 50%)";
  const draftFillColor = "hsla(330, 60%, 95%, 0.2)";

  let hoveredEdge: { x: number; y: number; shapeIndex: number; afterIndex: number } | null = null;

  $: polygonCreation =
    newShape.status === "creating" && newShape.type === CanvasShapeType.Polygon
      ? asPolygonCreation(newShape)
      : null;
  $: polygonPoints =
    polygonCreation?.phase === "drawing" && polygonCreation.points.length > 0
      ? [...polygonCreation.closedPolygons, polygonCreation.points]
      : (polygonCreation?.closedPolygons ?? []);
  $: {
    if (!polygonCreation || polygonCreation.phase !== "editing") {
      hoveredEdge = null;
    }
  }

  $: shouldRenderSavedPolygon =
    newShape.status === "saving" &&
    (newShape.type === CanvasShapeType.Polygon || newShape.type === CanvasShapeType.Mask) &&
    "polygonMode" in newShape;

  function getRelativePointerOnView() {
    const viewLayer = stage?.findOne(`#${viewRef.name}`);
    if (!(viewLayer instanceof Konva.Layer)) return null;
    return viewLayer?.getRelativePointerPosition();
  }

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
    const projected = { x: a.x + t * dx, y: a.y + t * dy };
    return { dist: Math.hypot(p.x - projected.x, p.y - projected.y), point: projected };
  }

  function findClosestEdge(pos: { x: number; y: number }, polygons: CanvasPolygonPoint[][]) {
    let bestDist = Number.POSITIVE_INFINITY;
    let bestShape = -1;
    let bestIdx = -1;
    let bestPoint = pos;

    for (let shapeIndex = 0; shapeIndex < polygons.length; shapeIndex++) {
      const polygon = polygons[shapeIndex];
      for (let pointIndex = 0; pointIndex < polygon.length; pointIndex++) {
        const start = polygon[pointIndex];
        const end = polygon[(pointIndex + 1) % polygon.length];
        const { dist, point } = projectOnSegment(pos, start, end);
        if (dist < bestDist) {
          bestDist = dist;
          bestShape = shapeIndex;
          bestIdx = pointIndex;
          bestPoint = point;
        }
      }
    }

    return { bestDist, bestShape, bestIdx, bestPoint };
  }

  function handlePolygonPointsClick(pointIndex: number, shapeIndex: number) {
    if (!polygonCreation || polygonCreation.phase !== "drawing") return;
    const inProgressIndex = polygonPoints.length - 1;
    if (shapeIndex !== inProgressIndex || pointIndex !== 0) return;
    const inProgressPolygon = polygonPoints[shapeIndex];
    if (!inProgressPolygon || inProgressPolygon.length < 3) return;

    const firstPoint = inProgressPolygon[0];
    onToolEvent({
      type: "pointerDown",
      button: 0,
      position: { x: firstPoint.x, y: firstPoint.y },
    });
  }

  function handlePolygonPointsDragMove(id: number, shapeIndex: number) {
    const pointNode = stage?.findOne(`#dot-${POLYGON_ID}-${shapeIndex}-${id}`);
    if (!(pointNode instanceof Konva.Circle)) return;
    const pos = pointNode.position();
    onToolEvent({
      type: "polygonMoveVertex",
      polygonIndex: shapeIndex,
      pointId: id,
      position: { x: pos.x, y: pos.y },
    });
  }

  function handleShapeMouseMove() {
    if (!polygonCreation || polygonCreation.phase !== "editing") {
      hoveredEdge = null;
      return;
    }

    const pos = getRelativePointerOnView();
    if (!pos) {
      hoveredEdge = null;
      return;
    }

    const threshold = EDGE_SNAP_PX / zoomFactor[viewRef.name];
    const { bestDist, bestShape, bestIdx, bestPoint } = findClosestEdge(
      pos,
      polygonCreation.closedPolygons,
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

  function handleEdgeClick(event: CustomEvent) {
    if (!polygonCreation || polygonCreation.phase !== "editing") return;

    const konvaEvent = event.detail as Konva.KonvaEventObject<MouseEvent>;
    konvaEvent.cancelBubble = true;

    if (hoveredEdge) {
      onToolEvent({
        type: "polygonInsertVertex",
        polygonIndex: hoveredEdge.shapeIndex,
        afterIndex: hoveredEdge.afterIndex,
        position: {
          x: Math.round(hoveredEdge.x),
          y: Math.round(hoveredEdge.y),
        },
      });
      hoveredEdge = null;
      return;
    }

    const pos = getRelativePointerOnView();
    if (!pos) return;
    onToolEvent({
      type: "pointerDown",
      button: 0,
      position: { x: Math.round(pos.x), y: Math.round(pos.y) },
    });
  }

  function handlePolygonDragEnd(event: CustomEvent<Konva.KonvaEventObject<DragEvent>>) {
    if (!polygonCreation || polygonCreation.phase !== "editing") return;

    const target = event.detail.target;
    if (!(target instanceof Konva.Group)) return;
    const { x, y } = target.position();
    const deltaX = Math.round(x);
    const deltaY = Math.round(y);
    target.position({ x: 0, y: 0 });
    target.getLayer()?.batchDraw();

    if (deltaX === 0 && deltaY === 0) return;

    onToolEvent({
      type: "polygonTranslate",
      delta: { x: deltaX, y: deltaY },
    });
  }

  function drawPolygonScene(ctx: Konva.Context, shape: Konva.Shape) {
    ctx.beginPath();

    const closedPolygons = polygonCreation?.closedPolygons ?? [];
    for (const polygon of closedPolygons) {
      if (polygon.length < 2) continue;
      ctx.moveTo(polygon[0].x, polygon[0].y);
      for (let i = 1; i < polygon.length; i++) {
        ctx.lineTo(polygon[i].x, polygon[i].y);
      }
      ctx.closePath();
    }

    const inProgress = polygonCreation?.phase === "drawing" ? polygonCreation.points : [];
    const hasCurrent = !!polygonCreation?.current;
    if (inProgress.length > 0) {
      ctx.moveTo(inProgress[0].x, inProgress[0].y);
      for (let i = 1; i < inProgress.length; i++) {
        ctx.lineTo(inProgress[i].x, inProgress[i].y);
      }
      if (hasCurrent) {
        ctx.lineTo(polygonCreation.current.x, polygonCreation.current.y);
      }
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
    if (!polygonCreation || polygonCreation.phase !== "editing") {
      return;
    }
    ctx.beginPath();
    for (const polygon of polygonCreation.closedPolygons) {
      if (polygon.length < 2) continue;
      ctx.moveTo(polygon[0].x, polygon[0].y);
      for (let i = 1; i < polygon.length; i++) {
        ctx.lineTo(polygon[i].x, polygon[i].y);
      }
      ctx.closePath();
    }
    ctx.fillStrokeShape(shape);
  }
</script>

{#if newShape.viewRef?.name === viewRef.name}
  <Group
    on:dragend={handlePolygonDragEnd}
    config={{
      id: "polygon-draft",
      draggable: polygonCreation?.phase === "editing",
    }}
  >
    {#if polygonCreation}
      <KonvaShape
        on:click={handleEdgeClick}
        on:mousemove={handleShapeMouseMove}
        on:mouseleave={handleShapeMouseLeave}
        config={{
          sceneFunc: drawPolygonScene,
          stroke: draftLineColor,
          strokeWidth: INPUTRECT_STROKEWIDTH / zoomFactor[viewRef.name],
          fill: draftFillColor,
          hitFunc: drawPolygonHit,
          listening: polygonCreation.phase === "editing",
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
      {#if hoveredEdge}
        <Circle
          config={{
            x: hoveredEdge.x,
            y: hoveredEdge.y,
            radius: 5 / zoomFactor[viewRef.name],
            fill: draftLineColor,
            stroke: "white",
            strokeWidth: 1.5 / zoomFactor[viewRef.name],
            listening: false,
          }}
        />
      {/if}
    {:else if shouldRenderSavedPolygon}
      <KonvaShape
        config={{
          sceneFunc: (ctx, shape) => sceneFunc(ctx, shape, getSavedSvg(newShape)),
          stroke: draftLineColor,
          strokeWidth: INPUTRECT_STROKEWIDTH / zoomFactor[viewRef.name],
          closed: true,
          fill: draftFillColor,
          listening: false,
        }}
      />
    {/if}
  </Group>
{/if}
