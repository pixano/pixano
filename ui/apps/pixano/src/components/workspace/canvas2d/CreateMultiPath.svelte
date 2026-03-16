<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import Konva from "konva";
  import { Circle, Group, Shape as KonvaShape } from "svelte-konva";

  import { DRAFT_FILL_COLOR, DRAFT_LINE_COLOR, EDGE_SNAP_PX } from "./konvaConstants";
  import PolygonVertices from "./PolygonVertices.svelte";
  import type { ToolEvent } from "$lib/tools";
  import type { Reference } from "$lib/types/dataset";
  import type { Point2D } from "$lib/types/geometry";
  import {
    ShapeType,
    type CreatePolygonShape,
    type CreatePolylineShape,
    type Shape,
  } from "$lib/types/shapeTypes";
  import type { PolygonVertex } from "$lib/types/shapeTypes";

  interface Props {
    viewRef: Reference;
    newShape: Shape;
    getRelativePointerOnView?: () => Point2D | null;
    zoomFactor: number;
    isInteracting?: boolean;
    onToolEvent?: (event: ToolEvent) => void;
  }

  let {
    viewRef,
    newShape,
    getRelativePointerOnView = () => null,
    zoomFactor,
    isInteracting = false,
    onToolEvent = () => {
      return;
    },
  }: Props = $props();

  const POLYGON_ID = "creating";

  type MultiPathCreation = CreatePolygonShape | CreatePolylineShape;
  const asMultiPathCreation = (shape: Shape): MultiPathCreation => shape as MultiPathCreation;
  const getSavedPolygonPoints = (shape: Shape): PolygonVertex[][] =>
    "polygonPoints" in shape && Array.isArray(shape.polygonPoints)
      ? shape.polygonPoints
      : "polylinePoints" in shape && Array.isArray(shape.polylinePoints)
        ? shape.polylinePoints
        : [];

  // eslint-disable-next-line @typescript-eslint/no-unsafe-assignment
  let hoveredEdge: { x: number; y: number; shapeIndex: number; afterIndex: number } | null =
    $state(null);

  let multiPathCreation = $derived(
    newShape.status === "creating" &&
      "type" in newShape &&
      (newShape.type === ShapeType.polygon || newShape.type === ShapeType.polyline)
      ? asMultiPathCreation(newShape)
      : null,
  );

  /** Whether paths are closed (polygon) or open (polyline). */
  let isClosed = $derived(multiPathCreation ? multiPathCreation.type === ShapeType.polygon : false);

  let polygonPoints = $derived(
    multiPathCreation?.phase === "drawing" && multiPathCreation.points.length > 0
      ? [...multiPathCreation.closedPolygons, multiPathCreation.points]
      : (multiPathCreation?.closedPolygons ?? []),
  );
  $effect(() => {
    if (!multiPathCreation || multiPathCreation.phase !== "editing") {
      hoveredEdge = null;
    }
  });

  let shouldRenderSavedPolygon = $derived(
    newShape.status === "saving" &&
      "type" in newShape &&
      (newShape.type === ShapeType.polygon ||
        newShape.type === ShapeType.polyline ||
        newShape.type === ShapeType.mask) &&
      ("polygonMode" in newShape || "polylinePoints" in newShape),
  );

  /** Whether the saved shape is closed. */
  let savedIsClosed = $derived(
    newShape.status === "saving" && "type" in newShape
      ? newShape.type === ShapeType.polygon || newShape.type === ShapeType.mask
      : false,
  );

  function projectOnSegment(p: Point2D, a: Point2D, b: Point2D) {
    const dx = b.x - a.x;
    const dy = b.y - a.y;
    const len2 = dx * dx + dy * dy;
    if (len2 === 0) return { dist: Math.hypot(p.x - a.x, p.y - a.y), point: a };
    let t = ((p.x - a.x) * dx + (p.y - a.y) * dy) / len2;
    t = Math.max(0, Math.min(1, t));
    const projected = { x: a.x + t * dx, y: a.y + t * dy };
    return { dist: Math.hypot(p.x - projected.x, p.y - projected.y), point: projected };
  }

  function findClosestEdge(pos: Point2D, polygons: PolygonVertex[][], closed: boolean) {
    let bestDist = Number.POSITIVE_INFINITY;
    let bestShape = -1;
    let bestIdx = -1;
    let bestPoint = pos;

    for (let shapeIndex = 0; shapeIndex < polygons.length; shapeIndex++) {
      const polygon = polygons[shapeIndex];
      // For open polylines, only iterate up to length-1 (no wrapping edge)
      const edgeCount = closed ? polygon.length : polygon.length - 1;
      for (let pointIndex = 0; pointIndex < edgeCount; pointIndex++) {
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
    if (!multiPathCreation || multiPathCreation.phase !== "drawing") return;
    // For open polylines, clicking a vertex does not close the sub-path.
    // Users press N to finish a sub-path instead.
    if (!isClosed) return;
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

  function handlePolygonPointsDragMove(
    id: number,
    shapeIndex: number,
    e: Konva.KonvaEventObject<DragEvent>,
  ) {
    const pos = (e.target as Konva.Circle).position();
    onToolEvent({
      type: "polygonMoveVertex",
      polygonIndex: shapeIndex,
      pointId: id,
      position: { x: Math.round(pos.x), y: Math.round(pos.y) },
    });
  }

  function handleShapeMouseMove() {
    if (isInteracting) {
      hoveredEdge = null;
      return;
    }
    if (!multiPathCreation || multiPathCreation.phase !== "editing") {
      hoveredEdge = null;
      return;
    }

    const pos = getRelativePointerOnView();
    if (!pos) {
      hoveredEdge = null;
      return;
    }

    const threshold = EDGE_SNAP_PX / zoomFactor;
    const { bestDist, bestShape, bestIdx, bestPoint } = findClosestEdge(
      pos,
      multiPathCreation.closedPolygons,
      isClosed,
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

  function handleEdgeClick(e: Konva.KonvaEventObject<MouseEvent>) {
    if (!multiPathCreation || multiPathCreation.phase !== "editing") return;

    e.cancelBubble = true;

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

  function handlePolygonDragEnd(e: Konva.KonvaEventObject<DragEvent>) {
    if (!multiPathCreation || multiPathCreation.phase !== "editing") return;

    const target = e.target;
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

    const closedPolygons = multiPathCreation?.closedPolygons ?? [];
    for (const polygon of closedPolygons) {
      if (polygon.length < 2) continue;
      ctx.moveTo(polygon[0].x, polygon[0].y);
      for (let i = 1; i < polygon.length; i++) {
        ctx.lineTo(polygon[i].x, polygon[i].y);
      }
      if (isClosed) {
        ctx.closePath();
      }
    }

    const inProgress = multiPathCreation?.phase === "drawing" ? multiPathCreation.points : [];
    const hasCurrent = !!multiPathCreation?.current;
    if (inProgress.length > 0) {
      ctx.moveTo(inProgress[0].x, inProgress[0].y);
      for (let i = 1; i < inProgress.length; i++) {
        ctx.lineTo(inProgress[i].x, inProgress[i].y);
      }
      if (hasCurrent) {
        ctx.lineTo(multiPathCreation.current.x, multiPathCreation.current.y);
      }
    }

    if (isClosed) {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const rawCtx = (ctx as any)._context as CanvasRenderingContext2D;
      const fillColor = shape.fill() as string;
      if (fillColor) {
        rawCtx.fillStyle = fillColor;
        rawCtx.fill("evenodd");
      }
    }
    ctx.strokeShape(shape);
  }

  function drawPolygonHit(ctx: Konva.Context, shape: Konva.Shape) {
    if (!multiPathCreation || multiPathCreation.phase !== "editing") {
      return;
    }
    ctx.beginPath();
    for (const polygon of multiPathCreation.closedPolygons) {
      if (polygon.length < 2) continue;
      ctx.moveTo(polygon[0].x, polygon[0].y);
      for (let i = 1; i < polygon.length; i++) {
        ctx.lineTo(polygon[i].x, polygon[i].y);
      }
      if (isClosed) {
        ctx.closePath();
      }
    }
    if (isClosed) {
      ctx.fillStrokeShape(shape);
    } else {
      ctx.strokeShape(shape);
    }
  }
</script>

{#if "viewRef" in newShape && newShape.viewRef?.name === viewRef.name}
  <Group
    ondragend={handlePolygonDragEnd}
    id="polygon-draft"
    draggable={multiPathCreation?.phase === "editing"}
  >
    {#if multiPathCreation}
      <KonvaShape
        onclick={handleEdgeClick}
        onmousemove={handleShapeMouseMove}
        onmouseleave={handleShapeMouseLeave}
        sceneFunc={drawPolygonScene}
        stroke={DRAFT_LINE_COLOR}
        strokeScaleEnabled={false}
        perfectDrawEnabled={!isInteracting}
        shadowForStrokeEnabled={!isInteracting}
        fill={isClosed ? DRAFT_FILL_COLOR : undefined}
        hitFunc={drawPolygonHit}
        listening={multiPathCreation.phase === "editing"}
      />
      <PolygonVertices
        {viewRef}
        {zoomFactor}
        polygonId={POLYGON_ID}
        points={polygonPoints}
        onPointClick={handlePolygonPointsClick}
        onPointDragMove={handlePolygonPointsDragMove}
        onPointDragEnd={null}
      />
      {#if hoveredEdge}
        <Circle
          x={hoveredEdge.x}
          y={hoveredEdge.y}
          radius={5 / zoomFactor}
          fill={DRAFT_LINE_COLOR}
          stroke="white"
          strokeScaleEnabled={false}
          listening={false}
        />
      {/if}
    {:else if shouldRenderSavedPolygon}
      <KonvaShape
        sceneFunc={(ctx: Konva.Context, shape: Konva.Shape) => {
          const polygons = getSavedPolygonPoints(newShape);
          ctx.beginPath();
          for (const polygon of polygons) {
            if (polygon.length < 2) continue;
            ctx.moveTo(polygon[0].x, polygon[0].y);
            for (let i = 1; i < polygon.length; i++) {
              ctx.lineTo(polygon[i].x, polygon[i].y);
            }
            if (savedIsClosed) {
              ctx.closePath();
            }
          }
          if (savedIsClosed) {
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            const rawCtx = (ctx as any)._context as CanvasRenderingContext2D;
            const fillColor = shape.fill() as string;
            if (fillColor) {
              rawCtx.fillStyle = fillColor;
              rawCtx.fill("evenodd");
            }
          }
          ctx.strokeShape(shape);
        }}
        stroke={DRAFT_LINE_COLOR}
        strokeScaleEnabled={false}
        perfectDrawEnabled={!isInteracting}
        shadowForStrokeEnabled={!isInteracting}
        closed={savedIsClosed}
        fill={savedIsClosed ? DRAFT_FILL_COLOR : undefined}
        listening={false}
      />
    {/if}
  </Group>
{/if}
