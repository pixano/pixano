<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import type Konva from "konva";
  import { Group, Shape as KonvaShape } from "svelte-konva";

  import { getSmoothingEpsilonForZoom, sceneFunc, smoothSceneFunc } from "./konvaMaskOps";
  import PolygonVertices from "./PolygonVertices.svelte";
  import { ToolType, type SelectionTool } from "$lib/tools";
  import type { Mask, Reference } from "$lib/types/dataset";
  import { ShapeType, type Shape } from "$lib/types/shapeTypes";
  import type { PolygonVertex } from "$lib/types/shapeTypes";
  import {
    convertPointToSvg,
    hexToRGBA,
    isRawPolygonMask,
    parseSvgPath,
    runLengthEncode,
  } from "$lib/utils/maskUtils";

  interface Props {
    viewRef: Reference;
    newShape: Shape;
    currentImage: HTMLImageElement | ImageBitmap;
    mask: Mask;
    color: string;
    zoomFactor: number;
    selectedTool: SelectionTool;
    interactive?: boolean;
    disableCache?: boolean;
    smoothDisplay?: boolean;
    ghostOpacity?: number | undefined;
    onNewShapeChange?: (shape: Shape) => void;
  }

  let {
    viewRef,
    currentImage,
    mask,
    color,
    zoomFactor,
    selectedTool,
    interactive = true,
    disableCache = false,
    smoothDisplay = true,
    ghostOpacity = undefined,
    onNewShapeChange,
  }: Props = $props();

  let canEdit = $derived(mask.ui.displayControl.editing);
  let isRawPolygon = $derived(isRawPolygonMask(mask));
  let smoothingEpsilon = $derived(getSmoothingEpsilonForZoom(zoomFactor));

  const asPolygonPoint = (value: unknown): PolygonVertex | null => {
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

  const getRawPolygonPoints = (): PolygonVertex[][] => {
    const rawPoints = mask.ui.rawPoints;
    if (!Array.isArray(rawPoints)) return [];
    const polygons: PolygonVertex[][] = [];
    for (const polygon of rawPoints) {
      if (!Array.isArray(polygon)) return [];
      const parsedPolygon: PolygonVertex[] = [];
      for (const point of polygon) {
        const parsedPoint = asPolygonPoint(point);
        if (!parsedPoint) return [];
        parsedPolygon.push(parsedPoint);
      }
      polygons.push(parsedPolygon);
    }
    return polygons;
  };

  let simplifiedPoints: PolygonVertex[][] = $state<PolygonVertex[][]>([]);
  let simplifiedSvg = $derived(simplifiedPoints.map((point) => convertPointToSvg(point)));
  let shouldMaterializePolygonPoints = $derived(canEdit || isRawPolygon);
  let hasInitializedPolygonShape = false;
  let displayShapeComponent: { node: Konva.Shape } | undefined = $state();
  let staticCacheSignature = "";

  // Guard: only re-parse SVG when the svg reference actually changes
  let prevSvgRef: string[] | null = null;
  let prevRawPointsRef: unknown = null;

  $effect(() => {
    if (!shouldMaterializePolygonPoints) {
      hasInitializedPolygonShape = false;
      simplifiedPoints = [];
      return;
    }
    if (!hasInitializedPolygonShape) {
      const rawPoints = getRawPolygonPoints();
      simplifiedPoints =
        mask.data.inference_metadata?.geometry_mode === "polygon" && rawPoints.length > 0
          ? rawPoints
          : (mask.ui.svg ?? []).reduce(
              (acc, val) => [...acc, parseSvgPath(val)],
              [] as PolygonVertex[][],
            );
      prevSvgRef = mask.ui.svg ?? [];
      prevRawPointsRef = mask.ui.rawPoints;
      hasInitializedPolygonShape = true;
    }
  });

  $effect(() => {
    if (!shouldMaterializePolygonPoints) {
      return;
    }
    if (isRawPolygon) {
      if (mask.ui.rawPoints !== prevRawPointsRef) {
        prevRawPointsRef = mask.ui.rawPoints;
        const rawPoints = getRawPolygonPoints();
        if (rawPoints.length > 0) {
          simplifiedPoints = rawPoints;
        } else if ((mask.ui.svg ?? []) !== prevSvgRef) {
          prevSvgRef = mask.ui.svg ?? [];
          simplifiedPoints = (mask.ui.svg ?? []).reduce(
            (acc, val) => [...acc, parseSvgPath(val)],
            [] as PolygonVertex[][],
          );
        }
      }
    } else if ((mask.ui.svg ?? []) !== prevSvgRef) {
      prevSvgRef = mask.ui.svg ?? [];
      simplifiedPoints = (mask.ui.svg ?? []).reduce(
        (acc, val) => [...acc, parseSvgPath(val)],
        [] as PolygonVertex[][],
      );
    }
  });

  $effect(() => {
    const node = displayShapeComponent?.node;
    if (!node) return;
    const cacheable = !canEdit && !ghostOpacity && !disableCache;
    const signature = `${mask.id}|${mask.data.frame_id ?? ""}|${mask.ui.svg?.length ?? 0}|${color}|${mask.ui.strokeFactor ?? 1}|${smoothingEpsilon}`;
    if (cacheable) {
      if (staticCacheSignature !== signature || !node.isCached()) {
        node.clearCache();
        node.cache();
        staticCacheSignature = signature;
      }
      return;
    }
    if (node.isCached()) {
      node.clearCache();
    }
    staticCacheSignature = "";
  });

  const handlePointDragMove = (
    id: number,
    shapeIndex: number,
    e: Konva.KonvaEventObject<DragEvent>,
  ) => {
    const pos = (e.target as Konva.Circle).position();
    const newSimplifiedPoints = simplifiedPoints.map((points, pi) =>
      pi === shapeIndex
        ? points.map((point) =>
            point.id === id ? { ...point, x: Math.round(pos.x), y: Math.round(pos.y) } : point,
          )
        : points,
    );
    simplifiedPoints = newSimplifiedPoints;
  };

  const handlePointDragEnd = () => {
    const polygonSvg = simplifiedSvg;

    if (mask.ui.displayControl.editing) {
      if (isRawPolygon) {
        onNewShapeChange?.({
          status: "editing",
          type: ShapeType.polygon,
          viewRef,
          shapeId: mask.id,
          masksImageSVG: polygonSvg,
          polygonPoints: simplifiedPoints,
        });
      } else {
        const counts = runLengthEncode(polygonSvg, currentImage.width, currentImage.height);
        onNewShapeChange?.({
          status: "editing",
          type: ShapeType.mask,
          viewRef,
          shapeId: mask.id,
          counts,
        });
      }
    }
  };

  const handlePolygonDragEnd = (e: Konva.KonvaEventObject<DragEvent>) => {
    const target = e.target as Konva.Group;
    if (target.id() !== `polygon-${mask.id}`) return;
    const moveX = target.x();
    const moveY = target.y();
    const newSimplifiedPoints = simplifiedPoints.map((points) =>
      points.map((point) => ({ ...point, x: point.x + moveX, y: point.y + moveY })),
    );
    target.position({ x: 0, y: 0 });
    target.getLayer()?.batchDraw();
    simplifiedPoints = newSimplifiedPoints;
    const svg = simplifiedPoints.map((point) => convertPointToSvg(point));
    // Re-emit editing with the moved polygon
    if (mask.ui.displayControl.editing) {
      if (isRawPolygon) {
        onNewShapeChange?.({
          status: "editing",
          type: ShapeType.polygon,
          viewRef,
          shapeId: mask.id,
          masksImageSVG: svg,
          polygonPoints: simplifiedPoints,
        });
      } else {
        const counts = runLengthEncode(svg, currentImage.width, currentImage.height);
        onNewShapeChange?.({
          status: "editing",
          type: ShapeType.mask,
          viewRef,
          shapeId: mask.id,
          counts,
        });
      }
    }
  };

  const onClick = () => {
    if (mask.ui.displayControl.highlighted !== "self") {
      onNewShapeChange?.({
        status: "editing",
        shapeId: mask.id,
        viewRef,
        top_entity_id: (mask.ui.top_entities ?? [])[0]?.id,
        highlighted: "self",
        type: ShapeType.none,
      });
    }
  };

  const drawRawPolygonScene = (ctx: Konva.Context, shape: Konva.Shape) => {
    ctx.beginPath();
    for (const polygon of simplifiedPoints) {
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
  ondragend={handlePolygonDragEnd}
  id={`polygon-${mask.id}`}
  draggable={canEdit}
  visible={!mask.ui.displayControl.hidden}
  opacity={ghostOpacity ?? mask.ui.opacity ?? 1}
  listening={ghostOpacity ? false : interactive && selectedTool.type === ToolType.Pan}
>
  {#if canEdit}
    <KonvaShape
      sceneFunc={(ctx: Konva.Context, shape: Konva.Shape) =>
        isRawPolygon ? drawRawPolygonScene(ctx, shape) : sceneFunc(ctx, shape, simplifiedSvg)}
      stroke={color}
      strokeWidth={2}
      strokeScaleEnabled={false}
      perfectDrawEnabled={false}
      shadowForStrokeEnabled={false}
      closed={true}
      fill={hexToRGBA(color, 0.5)}
    />
    <PolygonVertices
      {viewRef}
      {zoomFactor}
      polygonId={mask.id}
      points={simplifiedPoints}
      onPointClick={null}
      onPointDragMove={handlePointDragMove}
      onPointDragEnd={handlePointDragEnd}
    />
  {:else}
    <KonvaShape
      bind:this={displayShapeComponent}
      onclick={ghostOpacity ? undefined : onClick}
      sceneFunc={(ctx: Konva.Context, shape: Konva.Shape) =>
        isRawPolygon
          ? drawRawPolygonScene(ctx, shape)
          : smoothDisplay
            ? smoothSceneFunc(ctx, shape, mask.ui.svg ?? [], smoothingEpsilon)
            : sceneFunc(ctx, shape, mask.ui.svg ?? [])}
      stroke={color}
      strokeWidth={mask.ui.strokeFactor ?? 1}
      closed={true}
      perfectDrawEnabled={false}
      shadowForStrokeEnabled={false}
      fill={hexToRGBA(color, ghostOpacity ? 1.0 : 0.35)}
      shadowColor={color}
      shadowBlur={2}
      shadowOpacity={0.4}
      shadowEnabled={!ghostOpacity && smoothDisplay}
      id={mask.id}
    />
  {/if}
</Group>
