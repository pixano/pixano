<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { untrack } from "svelte";
  import type Konva from "konva";
  import { LazyBrush } from "lazy-brush";
  import { Image as KonvaImage } from "svelte-konva";

  import { mask_utils } from "$lib/models";
  import type { Reference } from "$lib/types/dataset";
  import type { Point2D } from "$lib/types/geometry";
  import { ShapeType, type SaveMaskShape } from "$lib/types/shapeTypes";
  import type { BrushSelectionTool } from "$lib/tools";
  import {
    bitmapToRle,
    drawBrushCircle,
    interpolatePoints,
    isMaskEmpty,
    rleToBitmap,
  } from "./brushOps";

  interface MaskRle {
    counts: number[];
    size: [number, number];
  }

  interface Props {
    viewRef: Reference;
    currentImage: HTMLImageElement;
    zoomFactor: number;
    selectedItemId: string;
    selectedTool: BrushSelectionTool;
    brushSettings: {
      brushRadius: number;
      lazyRadius: number;
      friction: number;
    };
    existingMaskRle?: MaskRle | null;
  }

  let {
    viewRef,
    currentImage,
    zoomFactor,
    selectedItemId,
    selectedTool,
    brushSettings,
    existingMaskRle = null,
  }: Props = $props();

  // Internal state
  let offscreenCanvas: HTMLCanvasElement;
  let offscreenCtx: CanvasRenderingContext2D;
  let displayCanvas: HTMLCanvasElement = $state();
  let displayCtx: CanvasRenderingContext2D;
  let lazyBrush: LazyBrush = $state();
  let isPainting = false;
  let lastBrushPos: Point2D | null = null;
  let rafId: number | null = null;
  let needsUpdate = false;
  let previousMode: BrushSelectionTool["mode"] | null = null;

  // Reference to the KonvaImage component for triggering repaints via batchDraw()
  let konvaImageRef: { node: Konva.Image } | undefined = $state();

  const MASK_COLOR = "rgba(255, 0, 80, 0.5)";

  // Effective radius scaled by zoom
  let effectiveRadius = $derived(brushSettings.brushRadius / (zoomFactor || 1));

  $effect(() => {
    // Track both currentImage and existingMaskRle so the effect re-runs on undo/redo
    const img = currentImage;
    const maskRle = existingMaskRle;

    untrack(() => {
      // Create offscreen canvas at image resolution
      offscreenCanvas = document.createElement("canvas");
      offscreenCanvas.width = img.width;
      offscreenCanvas.height = img.height;
      offscreenCtx = offscreenCanvas.getContext("2d")!;

      // Create reusable display canvas
      displayCanvas = document.createElement("canvas");
      displayCanvas.width = img.width;
      displayCanvas.height = img.height;
      displayCtx = displayCanvas.getContext("2d")!;

      // Initialize LazyBrush
      lazyBrush = new LazyBrush({
        radius: 0,
        enabled: false,
        initialPoint: { x: 0, y: 0 },
      });

      // Load existing mask if provided
      if (maskRle && maskRle.counts.length > 0) {
        const [height, width] = maskRle.size;
        rleToBitmap(maskRle.counts, width, height, offscreenCanvas);
        updateDisplay();
      }

      // Start render loop
      startRenderLoop();
    });

    return () => {
      if (rafId !== null) {
        cancelAnimationFrame(rafId);
      }
    };
  });

  // React to brush settings / zoom changes
  $effect(() => {
    if (lazyBrush) {
      const effectiveLazy = brushSettings.lazyRadius / (zoomFactor || 1);
      lazyBrush.setRadius(effectiveLazy);
      if (brushSettings.lazyRadius <= 0) {
        lazyBrush.disable();
      } else {
        lazyBrush.enable();
      }
    }
  });

  // Force a redraw when switching between pencil and eraser
  $effect(() => {
    if (selectedTool?.mode && selectedTool.mode !== previousMode) {
      previousMode = selectedTool.mode;
      needsUpdate = true;
    }
  });

  function startRenderLoop(): void {
    function loop(): void {
      if (needsUpdate) {
        updateDisplay();
        needsUpdate = false;
      }
      rafId = requestAnimationFrame(loop);
    }
    loop();
  }

  function updateDisplay(): void {
    if (!displayCtx || !offscreenCanvas) return;

    displayCtx.clearRect(0, 0, displayCanvas.width, displayCanvas.height);
    displayCtx.globalCompositeOperation = "source-over";
    displayCtx.drawImage(offscreenCanvas, 0, 0);
    displayCtx.globalCompositeOperation = "source-in";
    displayCtx.fillStyle = MASK_COLOR;
    displayCtx.fillRect(0, 0, displayCanvas.width, displayCanvas.height);

    // Trigger svelte-konva repaint without destroying/recreating the node
    konvaImageRef?.node?.getLayer()?.batchDraw();
  }

  // Public API — called from Canvas2D
  export function beginStroke(x: number, y: number): void {
    isPainting = true;
    const point = { x, y };
    lazyBrush.update(point, { both: true });
    const brushPos = lazyBrush.getBrushCoordinates();
    drawBrushCircle(offscreenCtx, brushPos.x, brushPos.y, effectiveRadius, selectedTool.mode);
    lastBrushPos = brushPos;
    needsUpdate = true;
  }

  export function updateStroke(x: number, y: number): void {
    if (!isPainting) return;
    const point = { x, y };
    lazyBrush.update(point, { friction: brushSettings.friction });

    if (lazyBrush.brushHasMoved()) {
      const brushPos = lazyBrush.getBrushCoordinates();
      if (lastBrushPos) {
        const spacing = Math.max(1, effectiveRadius * 0.25);
        const points = interpolatePoints(lastBrushPos, brushPos, spacing);
        for (const pt of points) {
          drawBrushCircle(offscreenCtx, pt.x, pt.y, effectiveRadius, selectedTool.mode);
        }
      }
      lastBrushPos = brushPos;
      needsUpdate = true;
    }
  }

  export function endStroke(): void {
    isPainting = false;
    lastBrushPos = null;
  }

  export function getMaskData(): SaveMaskShape | null {
    if (isMaskEmpty(offscreenCanvas)) return null;

    const counts = bitmapToRle(offscreenCanvas);
    const maskPolygons = mask_utils.generatePolygonSegments(counts, currentImage.height);
    const masksSVG = mask_utils.convertSegmentsToSVG(maskPolygons);

    return {
      status: "saving",
      masksImageSVG: masksSVG,
      rle: {
        counts,
        size: [currentImage.height, currentImage.width],
      },
      type: ShapeType.mask,
      viewRef,
      itemId: selectedItemId,
      imageWidth: currentImage.width,
      imageHeight: currentImage.height,
    };
  }

  export function clearCanvas(): void {
    if (offscreenCtx) {
      offscreenCtx.clearRect(0, 0, offscreenCanvas.width, offscreenCanvas.height);
      needsUpdate = true;
    }
  }

  export function destroy(): void {
    if (rafId !== null) {
      cancelAnimationFrame(rafId);
      rafId = null;
    }
  }

  export function getIsPainting(): boolean {
    return isPainting;
  }

  export function getBrushCoordinates(): Point2D | null {
    if (!lazyBrush) return null;
    return lazyBrush.getBrushCoordinates();
  }

  export function getPointerCoordinates(): Point2D | null {
    if (!lazyBrush) return null;
    return lazyBrush.getPointerCoordinates();
  }
</script>

<!--
  Declarative brush mask display. The displayCanvas is updated imperatively
  via requestAnimationFrame, then batchDraw() triggers a Konva repaint.
-->
{#if displayCanvas}
  <KonvaImage
    bind:this={konvaImageRef}
    image={displayCanvas}
    x={0}
    y={0}
    width={currentImage.width}
    height={currentImage.height}
    listening={false}
    id="brush-mask"
  />
{/if}
