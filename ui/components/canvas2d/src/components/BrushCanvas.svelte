<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import Konva from "konva";
  import { LazyBrush } from "lazy-brush";
  import { onDestroy, onMount } from "svelte";

  import { SaveShapeType, type BrushSelectionTool, type Reference, type Shape } from "@pixano/core";
  import { convertSegmentsToSVG, generatePolygonSegments } from "@pixano/models/src/mask_utils";

  import {
    bitmapToRle,
    drawBrushCircle,
    interpolatePoints,
    isMaskEmpty,
    rleToBitmap,
  } from "../api/brushApi";

  // Exports
  export let viewRef: Reference;
  export let stage: Konva.Stage;
  export let currentImage: HTMLImageElement;
  export let zoomFactor: Record<string, number>;
  export let selectedItemId: string;
  export let selectedTool: BrushSelectionTool;
  export let brushSettings: {
    brushRadius: number;
    lazyRadius: number;
    friction: number;
  };
  export let existingMaskRle: { counts: number[]; size: [number, number] } | null = null;

  // Internal state
  let offscreenCanvas: HTMLCanvasElement;
  let offscreenCtx: CanvasRenderingContext2D;
  let lazyBrush: LazyBrush;
  let isPainting = false;
  let konvaImage: Konva.Image | null = null;
  let lastBrushPos: { x: number; y: number } | null = null;
  let rafId: number | null = null;
  let needsUpdate = false;

  const MASK_COLOR = "rgba(255, 0, 80, 0.5)";

  onMount(() => {
    // Create offscreen canvas at image resolution
    offscreenCanvas = document.createElement("canvas");
    offscreenCanvas.width = currentImage.width;
    offscreenCanvas.height = currentImage.height;
    offscreenCtx = offscreenCanvas.getContext("2d")!;

    // Initialize LazyBrush
    lazyBrush = new LazyBrush({
      radius: brushSettings.lazyRadius,
      enabled: brushSettings.lazyRadius > 0,
      initialPoint: { x: 0, y: 0 },
    });

    // Load existing mask if provided
    if (existingMaskRle && existingMaskRle.counts.length > 0) {
      const [height, width] = existingMaskRle.size;
      rleToBitmap(existingMaskRle.counts, width, height, offscreenCanvas);
      updateKonvaImage();
    }

    // Start render loop
    startRenderLoop();
  });

  onDestroy(() => {
    if (rafId !== null) {
      cancelAnimationFrame(rafId);
    }
    if (konvaImage) {
      konvaImage.destroy();
      konvaImage = null;
    }
  });

  // Effective radius scaled by zoom: brushRadius is in screen pixels, effectiveRadius is in image pixels
  $: effectiveRadius = brushSettings.brushRadius / (zoomFactor[viewRef.name] || 1);

  // React to brush settings / zoom changes
  $: if (lazyBrush) {
    const effectiveLazy = brushSettings.lazyRadius / (zoomFactor[viewRef.name] || 1);
    lazyBrush.setRadius(effectiveLazy);
    if (brushSettings.lazyRadius <= 0) {
      lazyBrush.disable();
    } else {
      lazyBrush.enable();
    }
  }

  function startRenderLoop() {
    const loop = () => {
      if (needsUpdate) {
        updateKonvaImage();
        needsUpdate = false;
      }
      rafId = requestAnimationFrame(loop);
    };
    rafId = requestAnimationFrame(loop);
  }

  function updateKonvaImage() {
    const viewLayer: Konva.Layer = stage.findOne(`#${viewRef.name}`);
    if (!viewLayer) return;

    const masksGroup: Konva.Group = viewLayer.findOne(`#masks-${viewRef.name}`);
    if (!masksGroup) return;

    // Create a colored version of the mask for display
    const displayCanvas = document.createElement("canvas");
    displayCanvas.width = offscreenCanvas.width;
    displayCanvas.height = offscreenCanvas.height;
    const displayCtx = displayCanvas.getContext("2d");
    if (!displayCtx) return;

    // Draw the mask in green with transparency
    displayCtx.drawImage(offscreenCanvas, 0, 0);
    displayCtx.globalCompositeOperation = "source-in";
    displayCtx.fillStyle = MASK_COLOR;
    displayCtx.fillRect(0, 0, displayCanvas.width, displayCanvas.height);

    if (!konvaImage) {
      konvaImage = new Konva.Image({
        id: "brush-mask",
        image: displayCanvas,
        x: 0,
        y: 0,
        width: currentImage.width,
        height: currentImage.height,
        listening: false,
      });
      masksGroup.add(konvaImage);
    } else {
      konvaImage.image(displayCanvas);
    }

    viewLayer.batchDraw();
  }

  // Called from Canvas2D on pointerdown
  export function beginStroke(x: number, y: number) {
    isPainting = true;
    const point = { x, y };

    // Update lazy brush with both=true to sync pointer and brush on start
    lazyBrush.update(point, { both: true });
    const brushPos = lazyBrush.getBrushCoordinates();

    // Draw initial circle
    drawBrushCircle(offscreenCtx, brushPos.x, brushPos.y, effectiveRadius, selectedTool.mode);
    lastBrushPos = brushPos;
    needsUpdate = true;
  }

  // Called from Canvas2D on pointermove
  export function updateStroke(x: number, y: number) {
    if (!isPainting) return;

    const point = { x, y };
    lazyBrush.update(point, { friction: brushSettings.friction });

    if (lazyBrush.brushHasMoved()) {
      const brushPos = lazyBrush.getBrushCoordinates();

      if (lastBrushPos) {
        // Interpolate between last and current brush position
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

  // Called from Canvas2D on pointerup
  export function endStroke() {
    isPainting = false;
    lastBrushPos = null;
  }

  // Called to get mask data for saving — returns the shape data without assigning it
  export function getMaskData(): Shape | null {
    if (isMaskEmpty(offscreenCanvas)) return null;

    const counts = bitmapToRle(offscreenCanvas);
    const maskPolygons = generatePolygonSegments(counts, currentImage.height);
    const masksSVG = convertSegmentsToSVG(maskPolygons);

    return {
      status: "saving",
      masksImageSVG: masksSVG,
      rle: {
        counts,
        size: [currentImage.height, currentImage.width],
      },
      type: SaveShapeType.mask,
      viewRef,
      itemId: selectedItemId,
      imageWidth: currentImage.width,
      imageHeight: currentImage.height,
    };
  }

  // Called to clear the brush canvas
  export function clearCanvas() {
    if (offscreenCtx) {
      offscreenCtx.clearRect(0, 0, offscreenCanvas.width, offscreenCanvas.height);
      needsUpdate = true;
    }
  }

  // Called to cleanup when switching away from brush tool
  export function destroy() {
    if (konvaImage) {
      konvaImage.destroy();
      konvaImage = null;
    }
    if (rafId !== null) {
      cancelAnimationFrame(rafId);
      rafId = null;
    }
  }

  export function getIsPainting() {
    return isPainting;
  }

  export function getBrushCoordinates(): { x: number; y: number } | null {
    if (!lazyBrush) return null;
    return lazyBrush.getBrushCoordinates();
  }

  export function getPointerCoordinates(): { x: number; y: number } | null {
    if (!lazyBrush) return null;
    return lazyBrush.getPointerCoordinates();
  }
</script>
