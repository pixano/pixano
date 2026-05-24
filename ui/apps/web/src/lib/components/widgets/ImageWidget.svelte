<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import Konva from "konva";
  import { MousePointer2, Save, Square, Trash2 } from "lucide-svelte";
  import { getContext, onMount } from "svelte";

  import { buildBBoxCreate, buildBBoxUpdate, generateShortId } from "$lib/annotations/buildPayloads.js";
  import type {
    CoordsNorm,
    ImageWidgetOptions,
    ImageWidgetStorage,
    LocalBBox,
    ResourceMutation,
  } from "$lib/annotations/types.js";
  import { pickEntityLabel } from "$lib/annotations/types.js";
  import type { WorkspaceManager } from "$lib/workspace/workspaceManager.svelte.js";

  interface Props {
    widgetId: string;
    options: Record<string, unknown>;
    data?: Record<string, unknown>;
  }

  let { widgetId, options, data }: Props = $props();

  // The manager is provided via Svelte context by GridWorkspace when it mounts
  // each widget; see ui/apps/web/src/lib/components/grid/GridWorkspace.svelte.
  const manager = getContext<WorkspaceManager>("workspaceManager");
  // `widgetId` and `options` are $props but they never change for the lifetime
  // of the component (GridWorkspace re-mounts the component when the underlying
  // widget instance changes), so capturing them once is safe.
  // svelte-ignore state_referenced_locally
  const stableWidgetId = widgetId;
  const storage = manager.getStorage(stableWidgetId) as ImageWidgetStorage;
  // svelte-ignore state_referenced_locally
  const imgOptions = options as ImageWidgetOptions;

  let containerEl = $state<HTMLDivElement>(null!);
  let stage = $state<Konva.Stage | null>(null);
  let imageLoaded = $state(false);
  let imageError = $state(false);

  let imageLayer: Konva.Layer | null = null;
  let annotationLayer: Konva.Layer | null = null;
  let konvaImage: Konva.Image | null = null;
  let loadedImg: HTMLImageElement | null = null;
  let placeholderShapes: Konva.Node[] = [];

  // Map LocalBBox.id -> Konva.Rect used to render it on the annotation layer.
  const rectByBBoxId = new Map<string, Konva.Rect>();
  // Map LocalBBox.id -> Konva.Label rendered above the rect (category name,
  // etc.). Only present when we have a non-empty derived label.
  const labelByBBoxId = new Map<string, Konva.Label>();
  let transformer: Konva.Transformer | null = null;

  // Draft rectangle state while the user is drawing a new bbox.
  let draftRect: Konva.Rect | null = null;
  let draftOrigin: { x: number; y: number } | null = null;

  const PIXEL_THRESHOLD = 3;

  function imageFrame(): { x: number; y: number; w: number; h: number } | null {
    if (!konvaImage) return null;
    return {
      x: konvaImage.x(),
      y: konvaImage.y(),
      w: konvaImage.width(),
      h: konvaImage.height(),
    };
  }

  function normalizedRectToPixel(
    coords: CoordsNorm,
  ): { x: number; y: number; width: number; height: number } | null {
    const frame = imageFrame();
    if (!frame) return null;
    return {
      x: frame.x + coords[0] * frame.w,
      y: frame.y + coords[1] * frame.h,
      width: coords[2] * frame.w,
      height: coords[3] * frame.h,
    };
  }

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
    redrawBoxes();
  }

  function redrawPlaceholder() {
    if (!stage || !imageLayer) return;
    for (const node of placeholderShapes) node.destroy();
    placeholderShapes = [];
    drawPlaceholder(imageLayer, stage.width(), stage.height());
  }

  function makeBoxRect(bbox: LocalBBox): Konva.Rect | null {
    const pixel = normalizedRectToPixel(bbox.coordsNorm);
    if (!pixel) return null;
    const stroke = bbox.persisted ? "#22d3ee" : "#f59e0b";
    const rect = new Konva.Rect({
      x: pixel.x,
      y: pixel.y,
      width: pixel.width,
      height: pixel.height,
      stroke,
      strokeWidth: 2,
      dash: bbox.persisted ? undefined : [6, 4],
      draggable: true,
      name: "bbox",
    });
    rect.setAttr("bboxId", bbox.id);

    rect.on("click tap", (e) => {
      e.cancelBubble = true;
      selectBBox(bbox.id);
    });
    rect.on("dragmove", () => {
      const label = labelByBBoxId.get(bbox.id);
      if (label) positionLabelForRect(label, rect);
    });
    rect.on("dragend", () => {
      commitRectGeometry(bbox.id, rect);
      const label = labelByBBoxId.get(bbox.id);
      if (label) positionLabelForRect(label, rect);
    });
    rect.on("transform", () => {
      const label = labelByBBoxId.get(bbox.id);
      if (label) positionLabelForRect(label, rect);
    });
    rect.on("transformend", () => {
      // Normalize scale into width/height so future transforms remain stable.
      const sx = rect.scaleX();
      const sy = rect.scaleY();
      rect.width(Math.max(1, rect.width() * sx));
      rect.height(Math.max(1, rect.height() * sy));
      rect.scaleX(1);
      rect.scaleY(1);
      commitRectGeometry(bbox.id, rect);
      const label = labelByBBoxId.get(bbox.id);
      if (label) positionLabelForRect(label, rect);
    });

    return rect;
  }

  /**
   * Build a Konva.Label for a bbox based on its entity fields. Returns null
   * when there's nothing descriptive to show (e.g. draft boxes before the
   * entity has been persisted). Callers are responsible for positioning.
   */
  function makeBoxLabel(bbox: LocalBBox): Konva.Label | null {
    const text = pickEntityLabel(bbox.entity);
    if (!text) return null;
    const stroke = bbox.persisted ? "#22d3ee" : "#f59e0b";
    const label = new Konva.Label({ listening: false });
    label.add(
      new Konva.Tag({
        fill: stroke,
        cornerRadius: 3,
      }),
    );
    label.add(
      new Konva.Text({
        text,
        fontSize: 12,
        fontFamily: "system-ui, sans-serif",
        fill: "#0f172a",
        padding: 3,
      }),
    );
    return label;
  }

  function positionLabelForRect(label: Konva.Label, rect: Konva.Rect) {
    // Anchor the label tag to the top-left corner of the box, with its
    // bottom edge touching the top stroke so it sits visually above the box.
    const { x, y } = rect.position();
    const labelHeight = label.height();
    label.position({ x, y: y - labelHeight - 1 });
  }

  function redrawBoxes() {
    if (!annotationLayer) return;

    const activeIds = new Set<string>();
    for (const bbox of storage.bboxes) {
      activeIds.add(bbox.id);
      let rect = rectByBBoxId.get(bbox.id);
      if (!rect) {
        rect = makeBoxRect(bbox) ?? undefined;
        if (!rect) continue;
        annotationLayer.add(rect);
        rectByBBoxId.set(bbox.id, rect);
      } else {
        const pixel = normalizedRectToPixel(bbox.coordsNorm);
        if (pixel) {
          rect.position({ x: pixel.x, y: pixel.y });
          rect.width(pixel.width);
          rect.height(pixel.height);
        }
        rect.stroke(bbox.persisted ? "#22d3ee" : "#f59e0b");
        rect.dash(bbox.persisted ? [] : [6, 4]);
      }

      // Keep the label in sync: create it lazily when entity info shows up
      // (e.g. after a draft is persisted and gets an entity assigned), and
      // reposition existing labels to follow the rect.
      let label = labelByBBoxId.get(bbox.id);
      if (!label) {
        label = makeBoxLabel(bbox) ?? undefined;
        if (label) {
          annotationLayer.add(label);
          labelByBBoxId.set(bbox.id, label);
        }
      }
      if (label) positionLabelForRect(label, rect);
    }

    for (const [id, rect] of rectByBBoxId) {
      if (!activeIds.has(id)) {
        rect.destroy();
        rectByBBoxId.delete(id);
      }
    }
    for (const [id, label] of labelByBBoxId) {
      if (!activeIds.has(id)) {
        label.destroy();
        labelByBBoxId.delete(id);
      }
    }

    syncTransformer();
    annotationLayer.batchDraw();
  }

  function syncTransformer() {
    if (!transformer) return;
    const id = storage.selectedId;
    if (!id) {
      transformer.nodes([]);
      transformer.getLayer()?.batchDraw();
      return;
    }
    const rect = rectByBBoxId.get(id);
    if (rect) {
      transformer.nodes([rect]);
      transformer.moveToTop();
    } else {
      transformer.nodes([]);
    }
    transformer.getLayer()?.batchDraw();
  }

  function selectBBox(id: string | null) {
    storage.selectedId = id;
    syncTransformer();
  }

  function commitRectGeometry(bboxId: string, rect: Konva.Rect) {
    const frame = imageFrame();
    if (!frame || frame.w <= 0 || frame.h <= 0) return;

    const bbox = storage.bboxes.find((b) => b.id === bboxId);
    if (!bbox) return;

    const x = (rect.x() - frame.x) / frame.w;
    const y = (rect.y() - frame.y) / frame.h;
    const w = rect.width() / frame.w;
    const h = rect.height() / frame.h;
    const coordsNorm: CoordsNorm = [x, y, w, h];
    bbox.coordsNorm = coordsNorm;

    if (bbox.persisted) {
      // Coalesce multiple edits on the same bbox into a single pending update.
      const ctx = {
        datasetId: imgOptions.datasetId,
        recordId: imgOptions.recordId,
        viewId: imgOptions.viewId,
      };
      const body = buildBBoxUpdate(ctx, bbox.id, bbox.entityId, coordsNorm);
      const existing = manager.pendingMutations.find(
        (m) => m.op === "update" && m.resource === "bboxes" && m.id === bbox.id,
      );
      if (existing && existing.op === "update") {
        existing.body = body;
      } else {
        manager.queueMutation({
          op: "update",
          resource: "bboxes",
          id: bbox.id,
          body,
          widgetId: stableWidgetId,
          localBBoxId: bbox.id,
        });
      }
    } else {
      // Still a pending-create box: rewrite its queued create body in place.
      const pending = manager.pendingMutations.find(
        (m) =>
          m.op === "create" &&
          m.resource === "bboxes" &&
          m.widgetId === stableWidgetId &&
          m.localBBoxId === bbox.id,
      );
      if (pending && pending.op === "create") {
        (pending.body as Record<string, unknown>).coords = Array.from(coordsNorm);
      }
    }
  }

  function deleteSelected() {
    const id = storage.selectedId;
    if (!id) return;
    const bbox = storage.bboxes.find((b) => b.id === id);
    if (!bbox) return;

    if (bbox.persisted) {
      manager.queueMutation({
        op: "delete",
        resource: "bboxes",
        id: bbox.id,
        widgetId: stableWidgetId,
        localBBoxId: bbox.id,
      });
      manager.queueMutation({
        op: "delete",
        resource: "entities",
        id: bbox.entityId,
        widgetId: stableWidgetId,
        localBBoxId: bbox.id,
      });
    } else {
      manager.dropMutationsForLocalBBox(bbox.id);
    }

    storage.bboxes = storage.bboxes.filter((b) => b.id !== bbox.id);
    storage.selectedId = null;
    redrawBoxes();
  }

  function beginDraw(event: Konva.KonvaEventObject<MouseEvent>) {
    if (storage.mode !== "draw-bbox" || !stage || !annotationLayer) return;
    event.cancelBubble = true;
    const pos = stage.getPointerPosition();
    if (!pos) return;
    draftOrigin = pos;
    draftRect = new Konva.Rect({
      x: pos.x,
      y: pos.y,
      width: 0,
      height: 0,
      stroke: "#f59e0b",
      strokeWidth: 2,
      dash: [6, 4],
      listening: false,
    });
    annotationLayer.add(draftRect);
    annotationLayer.batchDraw();
  }

  function updateDraw() {
    if (!draftRect || !draftOrigin || !stage || !annotationLayer) return;
    const pos = stage.getPointerPosition();
    if (!pos) return;
    const x = Math.min(pos.x, draftOrigin.x);
    const y = Math.min(pos.y, draftOrigin.y);
    const w = Math.abs(pos.x - draftOrigin.x);
    const h = Math.abs(pos.y - draftOrigin.y);
    draftRect.position({ x, y });
    draftRect.width(w);
    draftRect.height(h);
    annotationLayer.batchDraw();
  }

  function endDrawFinalize() {
    if (!draftRect || !draftOrigin) return;

    const rectX = draftRect.x();
    const rectY = draftRect.y();
    const width = draftRect.width();
    const height = draftRect.height();

    draftRect.destroy();
    draftRect = null;
    draftOrigin = null;
    annotationLayer?.batchDraw();

    if (width < PIXEL_THRESHOLD || height < PIXEL_THRESHOLD) {
      storage.mode = "select";
      return;
    }

    const frame = imageFrame();
    if (!frame || frame.w <= 0 || frame.h <= 0) {
      storage.mode = "select";
      return;
    }

    // Clamp the rect to the image bounds.
    const clampedLeft = Math.max(frame.x, rectX);
    const clampedTop = Math.max(frame.y, rectY);
    const clampedRight = Math.min(frame.x + frame.w, rectX + width);
    const clampedBottom = Math.min(frame.y + frame.h, rectY + height);
    const clampedW = clampedRight - clampedLeft;
    const clampedH = clampedBottom - clampedTop;

    if (clampedW < PIXEL_THRESHOLD || clampedH < PIXEL_THRESHOLD) {
      storage.mode = "select";
      return;
    }

    const coordsNorm: CoordsNorm = [
      (clampedLeft - frame.x) / frame.w,
      (clampedTop - frame.y) / frame.h,
      clampedW / frame.w,
      clampedH / frame.h,
    ];

    const localId = generateShortId();
    const { entityId, bboxId, mutations } = buildBBoxCreate(
      {
        datasetId: imgOptions.datasetId,
        recordId: imgOptions.recordId,
        viewId: imgOptions.viewId,
      },
      coordsNorm,
      { widgetId: stableWidgetId, localBBoxId: localId },
    );
    void entityId;

    const bbox: LocalBBox = {
      id: localId,
      entityId,
      coordsNorm,
      persisted: false,
    };
    storage.bboxes.push(bbox);

    for (const m of mutations) {
      // Tag the bbox mutation with the real bbox id so the backend resource
      // url can later match on update/delete.
      if (m.op === "create" && m.resource === "bboxes") {
        (m as ResourceMutation & { body: Record<string, unknown> }).body.id = bboxId;
      }
      manager.queueMutation(m);
    }

    storage.mode = "select";
    storage.selectedId = localId;
    redrawBoxes();
  }

  function cancelDraft() {
    if (draftRect) {
      draftRect.destroy();
      annotationLayer?.batchDraw();
    }
    draftRect = null;
    draftOrigin = null;
    storage.mode = "select";
  }

  function onStageMouseDown(event: Konva.KonvaEventObject<MouseEvent>) {
    if (storage.mode === "draw-bbox") {
      beginDraw(event);
      return;
    }
    // In select mode, clicking the stage background clears selection.
    if (event.target === stage) {
      selectBBox(null);
    }
  }

  function onStageMouseMove() {
    if (storage.mode === "draw-bbox" && draftRect) {
      updateDraw();
    }
  }

  function onStageMouseUp() {
    if (storage.mode === "draw-bbox" && draftRect) {
      endDrawFinalize();
    }
  }

  function onWindowKeyDown(e: KeyboardEvent) {
    if (e.key === "Escape") {
      if (draftRect) cancelDraft();
      else selectBBox(null);
    } else if ((e.key === "Delete" || e.key === "Backspace") && storage.selectedId) {
      // Ignore when the user is typing in an input field.
      const target = e.target as HTMLElement | null;
      if (target && (target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.isContentEditable)) {
        return;
      }
      e.preventDefault();
      deleteSelected();
    }
  }

  onMount(() => {
    if (!containerEl) return;

    const { width, height } = containerEl.getBoundingClientRect();

    stage = new Konva.Stage({
      container: containerEl,
      width: width || 400,
      height: height || 300,
    });

    imageLayer = new Konva.Layer();
    annotationLayer = new Konva.Layer();
    stage.add(imageLayer);
    stage.add(annotationLayer);

    transformer = new Konva.Transformer({
      rotateEnabled: false,
      anchorStroke: "#22d3ee",
      anchorFill: "#0f172a",
      borderStroke: "#22d3ee",
      keepRatio: false,
      ignoreStroke: true,
    });
    annotationLayer.add(transformer);

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
        redrawBoxes();
      };
      img.onerror = () => {
        imageError = true;
      };
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
      transformer?.destroy();
      transformer = null;
      for (const rect of rectByBBoxId.values()) rect.destroy();
      rectByBBoxId.clear();
      for (const label of labelByBBoxId.values()) label.destroy();
      labelByBBoxId.clear();
      stage?.destroy();
      stage = null;
      imageLayer = null;
      annotationLayer = null;
      konvaImage = null;
      loadedImg = null;
      placeholderShapes = [];
    };
  });

  // Apply cursor changes based on mode.
  $effect(() => {
    if (!containerEl) return;
    containerEl.style.cursor = storage.mode === "draw-bbox" ? "crosshair" : "default";
  });

  // Re-render annotations when the bbox list changes.
  $effect(() => {
    void storage.bboxes.length;
    void storage.selectedId;
    if (imageLoaded) redrawBoxes();
  });

  function drawPlaceholder(layer: Konva.Layer, width: number, height: number) {
    const gridSize = 30;
    const add = (node: Konva.Node) => {
      layer.add(node as Konva.Shape);
      placeholderShapes.push(node);
    };

    for (let x = 0; x < width; x += gridSize) {
      add(
        new Konva.Line({
          points: [x, 0, x, height],
          stroke: "rgba(255,255,255,0.05)",
          strokeWidth: 1,
        }),
      );
    }
    for (let y = 0; y < height; y += gridSize) {
      add(
        new Konva.Line({
          points: [0, y, width, y],
          stroke: "rgba(255,255,255,0.05)",
          strokeWidth: 1,
        }),
      );
    }

    add(
      new Konva.Text({
        text: "Image Canvas",
        x: 0,
        y: height / 2 - 12,
        width: width,
        align: "center",
        fontSize: 16,
        fill: "rgba(255,255,255,0.3)",
        fontFamily: "system-ui, sans-serif",
      }),
    );

    layer.draw();
  }

  const hasSelection = $derived(storage.selectedId !== null);
  // Count unique pending boxes for this widget, not raw mutations: creating a
  // single bbox queues two mutations (entity + bbox) that share the same
  // localBBoxId, so we deduplicate on that to get the user-visible count.
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
      class="rounded p-1 text-muted-foreground hover:bg-accent hover:text-accent-foreground {storage.mode ===
      'select'
        ? 'bg-accent text-accent-foreground'
        : ''}"
    >
      <MousePointer2 class="h-3.5 w-3.5" />
    </button>
    <button
      type="button"
      onclick={() => (storage.mode = storage.mode === "draw-bbox" ? "select" : "draw-bbox")}
      title="Add box annotation (R)"
      class="rounded p-1 text-muted-foreground hover:bg-accent hover:text-accent-foreground {storage.mode ===
      'draw-bbox'
        ? 'bg-accent text-accent-foreground'
        : ''}"
    >
      <Square class="h-3.5 w-3.5" />
    </button>
    <span class="mx-1 h-4 w-px bg-border"></span>
    <button
      type="button"
      onclick={deleteSelected}
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
