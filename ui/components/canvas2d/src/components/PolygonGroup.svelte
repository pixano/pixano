<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import Konva from "konva";
  import { Group, Shape as KonvaShape } from "svelte-konva";

  import { ToolType, type SelectionTool } from "@pixano/tools";

  import {
    convertPointToSvg,
    hexToRGBA,
    parseSvgPath,
    runLengthEncode,
    sceneFunc,
    smoothSceneFunc,
  } from "../api/maskApi";
  import {
    CanvasShapeType,
    type CanvasMask,
    type CanvasReference,
    type CanvasShape,
  } from "../lib/types/canvasData";
  import type { PolygonGroupPoint, PolygonShape } from "../lib/types/canvas2dTypes";
  import PolygonPoints from "./PolygonPoints.svelte";

  // Exports
  export let viewRef: CanvasReference;
  export let newShape: CanvasShape;
  export let stage: Konva.Stage;
  export let currentImage: HTMLImageElement;
  export let mask: CanvasMask;
  export let color: string;
  export let zoomFactor: Record<string, number>;
  export let selectedTool: SelectionTool;
  export let ghostOpacity: number | undefined = undefined;

  let canEdit = false;
  let isRawPolygon = false;
  const asPolygonPoint = (value: unknown): PolygonGroupPoint | null => {
    if (
      typeof value === "object" &&
      value !== null &&
      "x" in value &&
      "y" in value &&
      "id" in value &&
      typeof value.x === "number" &&
      typeof value.y === "number" &&
      typeof value.id === "number"
    ) {
      return { x: value.x, y: value.y, id: value.id };
    }
    return null;
  };
  const getRawPolygonPoints = (): PolygonGroupPoint[][] => {
    const rawPoints = mask.ui.rawPoints;
    if (!Array.isArray(rawPoints)) return [];
    const polygons: PolygonGroupPoint[][] = [];
    for (const polygon of rawPoints) {
      if (!Array.isArray(polygon)) return [];
      const parsedPolygon: PolygonGroupPoint[] = [];
      for (const point of polygon) {
        const parsedPoint = asPolygonPoint(point);
        if (!parsedPoint) return [];
        parsedPolygon.push(parsedPoint);
      }
      polygons.push(parsedPolygon);
    }
    return polygons;
  };
  let polygonShape: PolygonShape = {
    simplifiedSvg: mask.ui.svg,
    simplifiedPoints:
      mask.data.inference_metadata?.geometry_mode === "polygon" && getRawPolygonPoints().length > 0
        ? getRawPolygonPoints()
        : mask.ui.svg.reduce((acc, val) => [...acc, parseSvgPath(val)], [] as PolygonGroupPoint[][]),
  };

  $: canEdit = mask.ui.displayControl.editing;
  $: isRawPolygon = mask.data.inference_metadata?.geometry_mode === "polygon";

  // Guard: only re-parse SVG when the svg reference actually changes
  let prevSvgRef: string[] | null = null;
  let prevRawPointsRef: unknown = null;
  $: {
    if (isRawPolygon) {
      if (mask.ui.rawPoints !== prevRawPointsRef) {
        prevRawPointsRef = mask.ui.rawPoints;
        const rawPoints = getRawPolygonPoints();
        if (rawPoints.length > 0) {
          polygonShape.simplifiedPoints = rawPoints;
        } else if (mask.ui.svg !== prevSvgRef) {
          prevSvgRef = mask.ui.svg;
          polygonShape.simplifiedPoints = mask.ui.svg.reduce(
            (acc, val) => [...acc, parseSvgPath(val)],
            [] as PolygonGroupPoint[][],
          );
        }
      }
    } else if (mask.ui.svg !== prevSvgRef) {
      prevSvgRef = mask.ui.svg;
      polygonShape.simplifiedPoints = mask.ui.svg.reduce(
        (acc, val) => [...acc, parseSvgPath(val)],
        [] as PolygonGroupPoint[][],
      );
    }
  }

  $: polygonShape.simplifiedSvg = polygonShape.simplifiedPoints.map((point) =>
    convertPointToSvg(point),
  );

  const handlePolygonPointsDragMove = (id: number, i: number) => {
    const pos = stage.findOne(`#dot-${mask.id}-${i}-${id}`).position();
    const newSimplifiedPoints = polygonShape.simplifiedPoints.map((points, pi) =>
      pi === i
        ? points.map((point) => (point.id === id ? { ...point, x: pos.x, y: pos.y } : point))
        : points,
    );
    polygonShape.simplifiedPoints = newSimplifiedPoints;
  };

  const handlePolygonPointsDragEnd = (svg?: string[]) => {
    const polygonSvg = svg || polygonShape.simplifiedSvg;

    if (mask.ui.displayControl.editing) {
      const counts = isRawPolygon
        ? undefined
        : runLengthEncode(polygonSvg, currentImage.width, currentImage.height);
      newShape = {
        status: "editing",
        type: isRawPolygon ? CanvasShapeType.Polygon : CanvasShapeType.Mask,
        viewRef,
        shapeId: mask.id,
        ...(counts ? { counts } : {}),
        ...(isRawPolygon
          ? {
              masksImageSVG: polygonSvg,
              polygonPoints: polygonShape.simplifiedPoints,
            }
          : {}),
      };
    }
  };

  const handlePolygonDragEnd = (target: Konva.Group) => {
    if (target.id() !== `polygon-${mask.id}`) return;
    const moveX = target.x();
    const moveY = target.y();
    const newSimplifiedPoints = polygonShape.simplifiedPoints.map((points) =>
      points.map((point) => ({ ...point, x: point.x + moveX, y: point.y + moveY })),
    );
    const currentPolygon = stage.findOne(`#polygon-${mask.id}`);
    currentPolygon.position({ x: 0, y: 0 });
    polygonShape.simplifiedPoints = newSimplifiedPoints;
    const svg = polygonShape.simplifiedPoints.map((point) => convertPointToSvg(point));
    handlePolygonPointsDragEnd(svg);
  };

  const onClick = () => {
    if (mask.ui.displayControl.highlighted !== "self") {
      newShape = {
        status: "editing",
        shapeId: mask.id,
        viewRef,
        top_entity_id: mask.ui.top_entities[0].id,
        highlighted: "self",
        type: "none",
      };
    }
  };

  const drawRawPolygonScene = (ctx: Konva.Context, shape: Konva.Shape) => {
    ctx.beginPath();
    for (const polygon of polygonShape.simplifiedPoints) {
      if (polygon.length < 2) continue;
      ctx.moveTo(polygon[0].x, polygon[0].y);
      for (let i = 1; i < polygon.length; i++) {
        ctx.lineTo(polygon[i].x, polygon[i].y);
      }
      ctx.closePath();
    }
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const rawCtx = (ctx as any)._context as CanvasRenderingContext2D;
    rawCtx.fillStyle = shape.fill() as string;
    rawCtx.fill("evenodd");
    ctx.strokeShape(shape);
  };
</script>

<Group
  on:dragend={(e) => handlePolygonDragEnd(e.detail.target)}
  config={{
    id: `polygon-${mask.id}`,
    draggable: canEdit,
    visible: !mask.ui.displayControl.hidden,
    opacity: ghostOpacity ?? mask.ui.opacity,
    listening: ghostOpacity ? false : selectedTool.type === ToolType.Pan,
  }}
>
  {#if canEdit}
    <KonvaShape
      config={{
        sceneFunc: (ctx, shape) =>
          isRawPolygon
            ? drawRawPolygonScene(ctx, shape)
            : sceneFunc(ctx, shape, polygonShape.simplifiedSvg),
        stroke: color,
        strokeWidth: 2 / zoomFactor[viewRef.name],
        closed: true,
        fill: hexToRGBA(color, 0.5),
      }}
    />
    <PolygonPoints
      {viewRef}
      {stage}
      {zoomFactor}
      polygonId={mask.id}
      points={polygonShape.simplifiedPoints}
      handlePolygonPointsClick={null}
      {handlePolygonPointsDragMove}
      {handlePolygonPointsDragEnd}
    />
  {:else}
    <KonvaShape
      on:click={ghostOpacity ? undefined : onClick}
      config={{
        sceneFunc: (ctx, shape) =>
          isRawPolygon
            ? drawRawPolygonScene(ctx, shape)
            : smoothSceneFunc(ctx, shape, mask.ui.svg),
        stroke: color,
        strokeWidth: mask.ui.strokeFactor,
        closed: true,
        fill: hexToRGBA(color, ghostOpacity ? 1.0 : 0.35),
        shadowColor: color,
        shadowBlur: 2,
        shadowOpacity: 0.4,
        shadowEnabled: !ghostOpacity,
        id: mask.id,
      }}
    />
  {/if}
</Group>
