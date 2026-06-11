<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import Konva from "konva";
  import { MousePointer2, Save, Square, Trash2 } from "lucide-svelte";
  import { getContext, onMount } from "svelte";

  import type { ImageWidgetOptions, ImageWidgetStorage } from "$lib/annotations/types.js";
  import type { WorkspaceManager } from "$lib/workspace/workspaceManager.svelte.js";

  import { BBoxAnnotationLayer } from "./useBBoxAnnotationLayer.js";
  import { BBoxDrawPhase } from "./useBBoxDrawPhase.js";

  interface Props {
    widgetId: string;
    options: Record<string, unknown>;
    data?: Record<string, unknown>;
  }

  let { widgetId, options, data }: Props = $props();

  const manager = getContext<WorkspaceManager>("workspaceManager");
  // svelte-ignore state_referenced_locally
  const stableWidgetId = widgetId;
  const storage = manager.getStorage(stableWidgetId) as ImageWidgetStorage;
  // svelte-ignore state_referenced_locally
  const imgOptions = options as ImageWidgetOptions;

  let containerEl = $state<HTMLDivElement>(null!);
  let imageLoaded = $state(false);
  let imageError = $state(false);

  let stage: Konva.Stage | null = null;
  let imageLayer: Konva.Layer | null = null;
  let konvaImage: Konva.Image | null = null;
  let loadedImg: HTMLImageElement | null = null;
  let placeholderShapes: Konva.Node[] = [];

  let annotationRef: BBoxAnnotationLayer | null = null;
  let drawPhaseRef: BBoxDrawPhase | null = null;

  function fitImageToStage() {
    if (!stage || !konvaImage || !loadedImg) return;
    const sw = stage.width();
    const sh = stage.height();
    const scale = Math.min(sw / loadedImg.width, sh / loadedImg.height);
    const iw = loadedImg.width * scale;
    const ih = loadedImg.height * scale;
    konvaImage.width(iw);
    konvaImage.height(ih);
    konvaImage.x((sw - iw) / 2);
    konvaImage.y((sh - ih) / 2);
    imageLayer?.batchDraw();
    annotationRef?.redrawBoxes();
  }

  function redrawPlaceholder() {
    if (!stage || !imageLayer) return;
    for (const node of placeholderShapes) node.destroy();
    placeholderShapes = [];
    drawPlaceholder(imageLayer, stage.width(), stage.height());
  }

  function drawPlaceholder(layer: Konva.Layer, width: number, height: number) {
    const gridSize = 30;
    const add = (node: Konva.Node) => { layer.add(node as Konva.Shape); placeholderShapes.push(node); };
    for (let x = 0; x < width; x += gridSize) {
      add(new Konva.Line({ points: [x, 0, x, height], stroke: "rgba(255,255,255,0.05)", strokeWidth: 1 }));
    }
    for (let y = 0; y < height; y += gridSize) {
      add(new Konva.Line({ points: [0, y, width, y], stroke: "rgba(255,255,255,0.05)", strokeWidth: 1 }));
    }
    add(new Konva.Text({
      text: "Image Canvas",
      x: 0,
      y: height / 2 - 12,
      width,
      align: "center",
      fontSize: 16,
      fill: "rgba(255,255,255,0.3)",
      fontFamily: "system-ui, sans-serif",
    }));
    layer.draw();
  }

  function onStageMouseDown(event: Konva.KonvaEventObject<MouseEvent>) {
    if (storage.mode === "draw-bbox") {
      drawPhaseRef?.beginDraw(event);
      return;
    }
    if (event.target === stage) annotationRef?.selectBBox(null);
  }

  function onStageMouseMove() {
    if (storage.mode === "draw-bbox" && drawPhaseRef?.isDrawing) drawPhaseRef.updateDraw();
  }

  function onStageMouseUp() {
    if (storage.mode === "draw-bbox" && drawPhaseRef?.isDrawing) drawPhaseRef.endDrawFinalize();
  }

  function onWindowKeyDown(e: KeyboardEvent) {
    if (e.key === "Escape") {
      if (drawPhaseRef?.isDrawing) drawPhaseRef.cancelDraft();
      else annotationRef?.selectBBox(null);
    } else if ((e.key === "Delete" || e.key === "Backspace") && storage.selectedId) {
      const target = e.target as HTMLElement | null;
      if (target && (target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.isContentEditable)) return;
      e.preventDefault();
      annotationRef?.deleteSelected();
    }
  }

  onMount(() => {
    if (!containerEl) return;
    const { width, height } = containerEl.getBoundingClientRect();
    stage = new Konva.Stage({ container: containerEl, width: width || 400, height: height || 300 });

    imageLayer = new Konva.Layer();
    const annotationLayer = new Konva.Layer();
    stage.add(imageLayer);
    stage.add(annotationLayer);

    annotationRef = new BBoxAnnotationLayer(
      annotationLayer,
      () => konvaImage,
      storage,
      manager,
      stableWidgetId,
      imgOptions,
    );
    drawPhaseRef = new BBoxDrawPhase(
      annotationLayer,
      stage,
      storage,
      manager,
      stableWidgetId,
      imgOptions,
      () => konvaImage,
      () => annotationRef?.redrawBoxes(),
    );

    stage.on("mousedown touchstart", onStageMouseDown);
    stage.on("mousemove touchmove", onStageMouseMove);
    stage.on("mouseup touchend", onStageMouseUp);

    const imageUrl = data?.imageUrl as string | undefined;
    if (imageUrl) {
      const img = new Image();
      img.onload = () => {
        if (!stage || !imageLayer) return;
        loadedImg = img;
        konvaImage = new Konva.Image({ image: img, x: 0, y: 0, listening: false });
        imageLayer.add(konvaImage);
        fitImageToStage();
        imageLoaded = true;
        annotationRef?.redrawBoxes();
      };
      img.onerror = () => { imageError = true; };
      img.src = imageUrl;
    } else {
      drawPlaceholder(imageLayer, stage.width(), stage.height());
    }

    const resizeObserver = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const { width: w, height: h } = entry.contentRect;
        if (stage && w > 0 && h > 0) {
          stage.width(w);
          stage.height(h);
          if (konvaImage) {
            fitImageToStage();
          } else if (!imageUrl) {
            redrawPlaceholder();
          }
          stage.draw();
        }
      }
    });

    resizeObserver.observe(containerEl);
    window.addEventListener("keydown", onWindowKeyDown);

    return () => {
      resizeObserver.disconnect();
      window.removeEventListener("keydown", onWindowKeyDown);
      annotationRef?.destroy();
      annotationRef = null;
      drawPhaseRef = null;
      stage?.destroy();
      stage = null;
      imageLayer = null;
      konvaImage = null;
      loadedImg = null;
      placeholderShapes = [];
    };
  });

  $effect(() => {
    if (!containerEl) return;
    containerEl.style.cursor = storage.mode === "draw-bbox" ? "crosshair" : "default";
  });

  $effect(() => {
    void storage.bboxes.length;
    void storage.selectedId;
    if (imageLoaded) annotationRef?.redrawBoxes();
  });

  const hasSelection = $derived(storage.selectedId !== null);
  const widgetPending = $derived(
    new Set(
      manager.pendingMutations
        .filter((m) => m.widgetId === stableWidgetId && m.localBBoxId)
        .map((m) => m.localBBoxId as string),
    ).size,
  );
</script>

<div class="flex h-full flex-col bg-card">
  <!-- svelte-ignore a11y_no_static_element_interactions -->
  <div
    class="flex items-center gap-0.5 border-b border-border bg-muted/30 px-1.5 py-0.5"
    onpointerdown={(e) => e.stopPropagation()}
    aria-label="Image annotation tools"
  >
    <button
      type="button"
      onclick={() => (storage.mode = "select")}
      title="Select / move (V)"
      class="rounded p-1 text-muted-foreground hover:bg-accent hover:text-accent-foreground {storage.mode === 'select' ? 'bg-accent text-accent-foreground' : ''}"
    >
      <MousePointer2 class="h-3.5 w-3.5" />
    </button>
    <button
      type="button"
      onclick={() => (storage.mode = storage.mode === "draw-bbox" ? "select" : "draw-bbox")}
      title="Add box annotation (R)"
      class="rounded p-1 text-muted-foreground hover:bg-accent hover:text-accent-foreground {storage.mode === 'draw-bbox' ? 'bg-accent text-accent-foreground' : ''}"
    >
      <Square class="h-3.5 w-3.5" />
    </button>
    <span class="mx-1 h-4 w-px bg-border"></span>
    <button
      type="button"
      onclick={() => annotationRef?.deleteSelected()}
      disabled={!hasSelection}
      title="Delete selected (Del)"
      class="rounded p-1 text-muted-foreground hover:bg-destructive/20 hover:text-destructive disabled:opacity-40"
    >
      <Trash2 class="h-3.5 w-3.5" />
    </button>
    <div class="flex-1"></div>
    {#if widgetPending > 0}
      <span class="text-[10px] text-muted-foreground">{widgetPending} pending</span>
    {/if}
    <button
      type="button"
      onclick={() => manager.flushSave()}
      disabled={manager.pendingCount === 0 || manager.saving}
      title="Save annotations"
      class="flex items-center gap-1 rounded px-2 py-1 text-xs text-muted-foreground hover:bg-accent hover:text-accent-foreground disabled:opacity-40"
    >
      <Save class="h-3.5 w-3.5" />
      {manager.saving ? "Saving…" : "Save"}
    </button>
  </div>

  {#if manager.saveError}
    <div class="border-b border-destructive/40 bg-destructive/10 px-2 py-0.5 text-xs text-destructive">
      {manager.saveError}
    </div>
  {/if}

  {#if imageError}
    <div class="flex flex-1 items-center justify-center">
      <div class="text-center text-muted-foreground">
        <div class="mb-1 text-sm">Failed to load image</div>
        <div class="text-xs">{data?.imageUrl}</div>
      </div>
    </div>
  {:else}
    <div bind:this={containerEl} class="flex-1" style="min-height: 100px;"></div>
  {/if}
</div>
