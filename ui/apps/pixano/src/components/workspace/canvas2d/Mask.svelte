<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { untrack } from "svelte";
  import { LazyBrush } from "lazy-brush";
  import { Image as KonvaImage } from "svelte-konva";
  import type Konva from "konva";

  import { NEUTRAL_ENTITY_COLOR } from "$lib/constants/workspaceConstants";
  import type { Mask as DatasetMask, Reference } from "$lib/types/dataset";
  import { ToolType, type SelectionTool } from "$lib/tools";
  import { ShapeType, type Shape } from "$lib/types/shapeTypes";
  import type { Point2D } from "$lib/types/geometry";
  import {
    canvasAlphaToRle,
    dataUrlToBlob,
    getAlphaBoundingBox,
    rleFrString,
    rleToBitmapCanvas,
    resolveMaskBitmapSource,
    resolveMaskBounds,
  } from "$lib/utils/maskUtils";

  interface BrushSettings {
    brushRadius: number;
    lazyRadius: number;
    friction: number;
  }

  interface Props {
    viewRef: Reference;
    currentImage: HTMLImageElement | ImageBitmap;
    masks?: DatasetMask[];
    colorScale: (value: string) => string;
    selectedTool: SelectionTool;
    zoomFactor: number;
    selectedItemId?: string;
    brushSettings?: BrushSettings;
  }

  let {
    viewRef,
    currentImage,
    masks = [],
    colorScale,
    selectedTool,
    zoomFactor,
    selectedItemId = "",
    brushSettings = { brushRadius: 20, lazyRadius: 10, friction: 0.15 },
  }: Props = $props();

  const BRUSH_MASK_COLOR = "rgba(255, 0, 80, 0.5)";

  function clampDimension(value: number): number {
    return Number.isFinite(value) && value > 0 ? Math.floor(value) : 1;
  }

  type CanvasInfra = {
    baseCanvas: HTMLCanvasElement;
    baseCtx: CanvasRenderingContext2D;
    sharedCanvas: HTMLCanvasElement;
    sharedCtx: CanvasRenderingContext2D;
    draftCanvas: HTMLCanvasElement;
    draftCtx: CanvasRenderingContext2D;
    scratchCanvas: HTMLCanvasElement;
    scratchCtx: CanvasRenderingContext2D;
    tintCanvas: HTMLCanvasElement;
    tintCtx: CanvasRenderingContext2D;
    lazyBrush: LazyBrush;
  };

  function getRequiredContext2D(
    canvas: HTMLCanvasElement,
    options?: CanvasRenderingContext2DSettings,
  ): CanvasRenderingContext2D {
    const ctx = canvas.getContext("2d", options);
    if (!ctx) {
      throw new Error("Failed to get 2d context from canvas.");
    }
    return ctx;
  }

  function createCanvasInfra(width: number, height: number): CanvasInfra {
    const base = document.createElement("canvas");
    const shared = document.createElement("canvas");
    const draft = document.createElement("canvas");
    const scratch = document.createElement("canvas");
    const tint = document.createElement("canvas");

    base.width = width;
    base.height = height;
    shared.width = width;
    shared.height = height;
    draft.width = width;
    draft.height = height;
    scratch.width = width;
    scratch.height = height;
    tint.width = width;
    tint.height = height;

    return {
      baseCanvas: base,
      baseCtx: getRequiredContext2D(base),
      sharedCanvas: shared,
      sharedCtx: getRequiredContext2D(shared),
      draftCanvas: draft,
      draftCtx: getRequiredContext2D(draft, { willReadFrequently: true }),
      scratchCanvas: scratch,
      scratchCtx: getRequiredContext2D(scratch),
      tintCanvas: tint,
      tintCtx: getRequiredContext2D(tint),
      lazyBrush: new LazyBrush({
        radius: 0,
        enabled: false,
        initialPoint: { x: 0, y: 0 },
      }),
    };
  }

  function resizeCanvas(canvas: HTMLCanvasElement, width: number, height: number): void {
    if (canvas.width === width && canvas.height === height) return;
    canvas.width = width;
    canvas.height = height;
  }

  const canvasInfra = createCanvasInfra(1, 1);

  let konvaImageRef: { node: Konva.Image } | undefined = $state();

  let isPainting = false;
  let lastBrushPos: Point2D | null = null;
  let hasDraftContent = false;

  const imageCache = new Map<string, Promise<HTMLImageElement>>();
  let renderCycle = 0;

  function requestRedraw(): void {
    konvaImageRef?.node?.getLayer()?.batchDraw();
  }

  // Inlined from brushOps.ts
  function drawBrushCircle(
    ctx: CanvasRenderingContext2D,
    x: number,
    y: number,
    radius: number,
    mode: "draw" | "erase",
  ): void {
    ctx.globalCompositeOperation = mode === "draw" ? "source-over" : "destination-out";
    ctx.beginPath();
    ctx.arc(x, y, radius, 0, Math.PI * 2);
    ctx.fillStyle = "white";
    ctx.fill();
  }

  function interpolatePoints(p1: Point2D, p2: Point2D, spacing: number): Point2D[] {
    const dx = p2.x - p1.x;
    const dy = p2.y - p1.y;
    const dist = Math.sqrt(dx * dx + dy * dy);
    if (dist <spacing) return [p2];
    const points: Point2D[] = [];
    const steps = Math.ceil(dist / spacing);
    for (let i = 1; i <= steps; i += 1) {
      const t = i / steps;
      points.push({ x: p1.x + dx * t, y: p1.y + dy * t });
    }
    return points;
  }

  function paintPoint(x: number, y: number, radius: number, mode: "draw" | "erase"): void {
    const { draftCtx, sharedCtx } = canvasInfra;
    // Data layer (white alpha)
    drawBrushCircle(draftCtx, x, y, radius, mode);
    // Visual layer (pink or erase)
    if (mode === "erase") {
      drawBrushCircle(sharedCtx, x, y, radius, "erase");
      drawBrushCircle(canvasInfra.baseCtx, x, y, radius, "erase");
    } else {
      sharedCtx.globalCompositeOperation = "source-over";
      sharedCtx.beginPath();
      sharedCtx.arc(x, y, radius, 0, Math.PI * 2);
      sharedCtx.fillStyle = BRUSH_MASK_COLOR;
      sharedCtx.fill();
    }
    hasDraftContent = true;
    requestRedraw();
  }

  let effectiveRadius = $derived(brushSettings.brushRadius / (zoomFactor || 1));
  let maskFingerprint = $derived.by(() => {
    let fp = `${currentImage.width}x${currentImage.height}|`;
    for (const mask of masks) {
      const source =
        mask.ui.bitmapUrl ??
        resolveMaskBitmapSource({ data: mask.data, metadata: mask.data.inference_metadata }) ??
        "";
      const bounds =
        mask.ui.bounds ??
        resolveMaskBounds({ data: mask.data, metadata: mask.data.inference_metadata });
      const colorId =
        mask.ui.top_entities && mask.ui.top_entities.length > 0
          ? mask.ui.top_entities[0].id
          : mask.data.entity_id;
      const hasCanvas = mask.ui.bitmapCanvas ? "C" : "";
      fp += `${mask.id}:${hasCanvas}${source}:${bounds?.x ?? 0},${bounds?.y ?? 0},${bounds?.width ?? 0},${bounds?.height ?? 0}:${colorId}:${mask.ui.displayControl.hidden}:${mask.ui.displayControl.highlighted};`;
    }
    return fp;
  });

  function copyBaseToShared(): void {
    const { baseCtx, sharedCtx, baseCanvas, draftCanvas, tintCanvas, tintCtx } = canvasInfra;
    if (!baseCtx || !sharedCtx) return;
    sharedCtx.globalCompositeOperation = "source-over";
    sharedCtx.clearRect(0, 0, baseCanvas.width, baseCanvas.height);
    sharedCtx.drawImage(baseCanvas, 0, 0);
    if (hasDraftContent) {
      tintCtx.clearRect(0, 0, tintCanvas.width, tintCanvas.height);
      tintCtx.drawImage(draftCanvas, 0, 0);
      tintCtx.globalCompositeOperation = "source-in";
      tintCtx.fillStyle = BRUSH_MASK_COLOR;
      tintCtx.fillRect(0, 0, tintCanvas.width, tintCanvas.height);
      tintCtx.globalCompositeOperation = "source-over";
      sharedCtx.drawImage(tintCanvas, 0, 0);
    }
    requestRedraw();
  }

  function getOrLoadImage(src: string): Promise<HTMLImageElement> {
    const cached = imageCache.get(src);
    if (cached !== undefined) return cached;

    const next = new Promise<HTMLImageElement>((resolve, reject) => {
      const image = new Image();
      image.onload = () => resolve(image);
      image.onerror = () => reject(new Error(`Failed to load mask image: ${src}`));
      image.src = src;
    });

    imageCache.set(src, next);
    return next;
  }

  function ensureMaskBitmapCanvas(
    mask: DatasetMask,
    fallbackImage: HTMLImageElement | ImageBitmap,
  ): OffscreenCanvas | null {
    if (mask.ui.bitmapCanvas) return mask.ui.bitmapCanvas;

    let counts = mask.data.counts;
    if (typeof counts === "string") {
      try {
        counts = rleFrString(counts);
      } catch {
        return null;
      }
      mask.data.counts = counts;
    }

    if (!Array.isArray(counts)) return null;

    const sizeH = Number(mask.data.size?.[0]);
    const sizeW = Number(mask.data.size?.[1]);
    const h = Number.isFinite(sizeH) && sizeH > 0 ? Math.floor(sizeH) : fallbackImage.height;
    const w = Number.isFinite(sizeW) && sizeW > 0 ? Math.floor(sizeW) : fallbackImage.width;

    try {
      const canvas = rleToBitmapCanvas(counts, [h, w]);
      mask.ui.bitmapCanvas = canvas;
      return canvas;
    } catch {
      return null;
    }
  }

  async function redrawBaseLayerWith(
    infra: CanvasInfra,
    masksToRender: DatasetMask[],
    image: HTMLImageElement | ImageBitmap,
    colorScaleFn: (id: string) => string,
    cycle: number,
  ): Promise<void> {
    const { baseCtx, scratchCanvas, scratchCtx } = infra;
    if (!baseCtx || !scratchCtx) return;

    baseCtx.globalCompositeOperation = "source-over";
    baseCtx.clearRect(0, 0, image.width, image.height);
    if (scratchCanvas.width !== image.width || scratchCanvas.height !== image.height) {
      scratchCanvas.width = image.width;
      scratchCanvas.height = image.height;
    }

    for (const mask of masksToRender) {
      if (mask.ui.displayControl.hidden) continue;

      const bounds =
        mask.ui.bounds ??
        resolveMaskBounds({ data: mask.data, metadata: mask.data.inference_metadata }) ?? {
          x: 0,
          y: 0,
          width: image.width,
          height: image.height,
        };

      const colorId =
        mask.ui.top_entities && mask.ui.top_entities.length > 0
          ? mask.ui.top_entities[0].id
          : mask.data.entity_id;
      const isNeutralMask = mask.ui.displayControl.highlighted === "none";
      const color = isNeutralMask ? NEUTRAL_ENTITY_COLOR : colorScaleFn(colorId);
      const overlayAlpha = isNeutralMask ? 0.2 : 0.5;

      // Prioritize OffscreenCanvas (from RLE decode) -- avoids async Image loading
      let imageSource: CanvasImageSource | null = mask.ui.bitmapCanvas ?? null;
      let useFullCanvasSource = Boolean(mask.ui.bitmapCanvas);

      if (!imageSource) {
        const source =
          mask.ui.bitmapUrl ??
          resolveMaskBitmapSource({ data: mask.data, metadata: mask.data.inference_metadata });

        if (source) {
          try {
            imageSource = await getOrLoadImage(source);
          } catch {
            imageSource = null;
          }
        }

        if (!imageSource) {
          const lazyDecodedCanvas = ensureMaskBitmapCanvas(mask, image);
          if (lazyDecodedCanvas) {
            imageSource = lazyDecodedCanvas;
            useFullCanvasSource = true;
          }
        }
      }

      if (cycle !== renderCycle) return;
      if (!imageSource) continue;

      scratchCtx.clearRect(0, 0, image.width, image.height);

      // bitmapCanvas is full-size (from RLE decode) -- draw at origin
      // bitmapUrl images may be cropped -- draw at bounds
      if (useFullCanvasSource) {
        scratchCtx.drawImage(imageSource, 0, 0);
        scratchCtx.globalCompositeOperation = "source-in";
        scratchCtx.fillStyle = color;
        scratchCtx.globalAlpha = overlayAlpha;
        scratchCtx.fillRect(0, 0, image.width, image.height);
        scratchCtx.globalAlpha = 1.0;
      } else {
        scratchCtx.drawImage(imageSource, bounds.x, bounds.y, bounds.width, bounds.height);
        scratchCtx.globalCompositeOperation = "source-in";
        scratchCtx.fillStyle = color;
        scratchCtx.globalAlpha = overlayAlpha;
        scratchCtx.fillRect(bounds.x, bounds.y, bounds.width, bounds.height);
        scratchCtx.globalAlpha = 1.0;
      }
      scratchCtx.globalCompositeOperation = "source-over";

      baseCtx.drawImage(scratchCanvas, 0, 0);
    }

    copyBaseToShared();
  }

  function bakeActiveStroke(): void {
    if (!hasDraftContent) return;
    copyBaseToShared();
  }

  // Keep mask canvases stable across frame changes; only resize when dimensions change.
  $effect(() => {
    const width = clampDimension(currentImage.width);
    const height = clampDimension(currentImage.height);
    const resized =
      canvasInfra.baseCanvas.width !== width || canvasInfra.baseCanvas.height !== height;

    if (!resized) return;

    resizeCanvas(canvasInfra.baseCanvas, width, height);
    resizeCanvas(canvasInfra.sharedCanvas, width, height);
    resizeCanvas(canvasInfra.draftCanvas, width, height);
    resizeCanvas(canvasInfra.scratchCanvas, width, height);
    resizeCanvas(canvasInfra.tintCanvas, width, height);

    renderCycle += 1;
    isPainting = false;
    lastBrushPos = null;
    hasDraftContent = false;
  });

  // Cleanup on component destroy
  $effect(() => {
    return () => {
      renderCycle += 1;
      isPainting = false;
      lastBrushPos = null;
      hasDraftContent = false;
    };
  });

  // Redraw base layer when mask fingerprint changes
  $effect(() => {
    const fingerprint = maskFingerprint;
    const infra = canvasInfra;
    if (!fingerprint || !infra.baseCtx) return;

    const currentMasks = masks;
    const img = currentImage;
    const scale = colorScale;
    const cycle = ++renderCycle;

    const rafId = requestAnimationFrame(() => {
      if (cycle !== renderCycle) return;
      untrack(() => {
        void redrawBaseLayerWith(infra, currentMasks, img, scale, cycle);
      });
    });

    return () => {
      cancelAnimationFrame(rafId);
    };
  });

  // Sync lazy brush settings
  $effect(() => {
    const { lazyBrush } = canvasInfra;
    if (!lazyBrush) return;
    const effectiveLazy = brushSettings.lazyRadius / (zoomFactor || 1);
    lazyBrush.setRadius(effectiveLazy);
    if (brushSettings.lazyRadius <= 0) {
      lazyBrush.disable();
    } else {
      lazyBrush.enable();
    }
  });

  export function beginStroke(x: number, y: number): void {
    if (selectedTool.type !== ToolType.Brush) return;

    const { lazyBrush } = canvasInfra;
    isPainting = true;
    const point = { x, y };
    lazyBrush.update(point, { both: true });
    const brushPos = lazyBrush.getBrushCoordinates();

    paintPoint(brushPos.x, brushPos.y, Math.max(1, effectiveRadius), selectedTool.mode);
    lastBrushPos = brushPos;
  }

  export function updateStroke(x: number, y: number): void {
    if (!isPainting) return;
    if (selectedTool.type !== ToolType.Brush) return;

    const { lazyBrush } = canvasInfra;
    const point = { x, y };
    lazyBrush.update(point, { friction: brushSettings.friction });

    if (!lazyBrush.brushHasMoved()) return;

    const brushPos = lazyBrush.getBrushCoordinates();
    const spacing = Math.max(1, effectiveRadius * 0.25);
    const points = lastBrushPos ? interpolatePoints(lastBrushPos, brushPos, spacing) : [brushPos];
    const radius = Math.max(1, effectiveRadius);

    for (const pt of points) {
      paintPoint(pt.x, pt.y, radius, selectedTool.mode);
    }

    lastBrushPos = brushPos;
  }

  export function endStroke(): void {
    if (!isPainting) return;
    isPainting = false;
    lastBrushPos = null;
    bakeActiveStroke();
  }

  export function getMaskData(): Shape | null {
    const { draftCanvas } = canvasInfra;
    if (!draftCanvas || !hasDraftContent) return null;

    const maskDataUrl = draftCanvas.toDataURL("image/png");
    const maskBlob = dataUrlToBlob(maskDataUrl) ?? undefined;
    const maskBounds = getAlphaBoundingBox(draftCanvas) ?? undefined;
    const rle = canvasAlphaToRle(draftCanvas);

    return {
      status: "saving",
      type: ShapeType.mask,
      viewRef,
      itemId: selectedItemId,
      imageWidth: currentImage.width,
      imageHeight: currentImage.height,
      maskDataUrl,
      maskBlob,
      maskMimeType: "image/png",
      maskBounds,
      rle,
    };
  }

  export function clearCanvas(): void {
    const { draftCtx } = canvasInfra;
    if (!draftCtx) return;
    draftCtx.clearRect(0, 0, canvasInfra.draftCanvas.width, canvasInfra.draftCanvas.height);
    hasDraftContent = false;
    copyBaseToShared();
  }

  export function destroy(): void {
    isPainting = false;
    lastBrushPos = null;
  }

  export function getIsPainting(): boolean {
    return isPainting;
  }

  export function getBrushCoordinates(): Point2D | null {
    const { lazyBrush } = canvasInfra;
    if (!lazyBrush) return null;
    return lazyBrush.getBrushCoordinates();
  }

  export function getPointerCoordinates(): Point2D | null {
    const { lazyBrush } = canvasInfra;
    if (!lazyBrush) return null;
    return lazyBrush.getPointerCoordinates();
  }
</script>

<KonvaImage
  bind:this={konvaImageRef}
  image={canvasInfra.sharedCanvas}
  x={0}
  y={0}
  width={currentImage.width}
  height={currentImage.height}
  listening={false}
  id={`mask-layer-${viewRef.name}`}
/>
