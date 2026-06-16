<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import Konva from "konva";
  import { Save, Trash2 } from "lucide-svelte";
  import { getContext, onMount } from "svelte";

  import { ViewScopedAnnotations } from "$lib/annotations/annotationCollection.svelte.js";
  import { deleteLocalAnnotation } from "$lib/annotations/payloadBuilders.js";
  import {
    DEFAULT_TOOL_2D,
    getTool2D,
    RENDERER_FACTORIES_2D,
    TOOLS_2D,
  } from "$lib/annotations/tools/registry2d.js";
  import type { AnnotationRenderer2D, Scene2DContext, ToolHandler2D } from "$lib/annotations/tools/types2d.js";
  import type { ImageWidgetOptions, ImageWidgetStorage } from "$lib/annotations/types.js";
  import type { WorkspaceManager } from "$lib/workspace/workspaceManager.svelte.js";

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

  // This widget's window onto the record's shared annotation collection:
  // this view's 2D annotations plus record-scoped kinds (e.g. bbox3d).
  const annotations = new ViewScopedAnnotations(() => manager.annotations, imgOptions.viewId);

  let containerEl = $state<HTMLDivElement>(null!);
  let imageLoaded = $state(false);
  let imageError = $state(false);
  let sceneReady = $state(false);

  let stage: Konva.Stage | null = null;
  let imageLayer: Konva.Layer | null = null;
  let konvaImage: Konva.Image | null = null;
  let loadedImg: HTMLImageElement | null = null;
  let placeholderShapes: Konva.Node[] = [];

  let renderers: AnnotationRenderer2D[] = [];
  let sceneContext: Scene2DContext | null = null;
  let activeHandler: ToolHandler2D | null = null;

  function syncRenderers() {
    for (const renderer of renderers) renderer.sync();
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
    syncRenderers();
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

  function onWindowKeyDown(e: KeyboardEvent) {
    const target = e.target as HTMLElement | null;
    if (target && (target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.isContentEditable)) return;
    if (activeHandler?.onKeyDown?.(e)) e.preventDefault();
  }

  onMount(() => {
    if (!containerEl) return;
    const { width, height } = containerEl.getBoundingClientRect();
    stage = new Konva.Stage({ container: containerEl, width: width || 400, height: height || 300 });

    imageLayer = new Konva.Layer();
    const annotationLayer = new Konva.Layer();
    stage.add(imageLayer);
    stage.add(annotationLayer);

    sceneContext = {
      widgetId: stableWidgetId,
      buildContext: {
        datasetId: imgOptions.datasetId,
        recordId: imgOptions.recordId,
        viewId: imgOptions.viewId,
      },
      collection: annotations,
      mutations: {
        get pending() {
          return manager.pendingMutations;
        },
        queue: (m) => manager.queueMutation(m),
        upsertUpdate: (m) => manager.upsertUpdateMutation(m),
        patchPendingCreate: (id, resource, patch) => manager.patchPendingCreateMutation(id, resource, patch),
        dropForLocalAnnotation: (id) => void manager.dropMutationsForLocalAnnotation(id),
      },
      stage,
      annotationLayer,
      getKonvaImage: () => konvaImage,
      setActiveTool: (id) => {
        storage.activeToolId = id;
      },
      requestRedraw: () => syncRenderers(),
      beginPendingAnnotation: (pending) => manager.beginPendingAnnotation(pending),
      findEntity: (entityId) => manager.entities.find((e) => e.id === entityId),
    };

    renderers = RENDERER_FACTORIES_2D.map((factory) => factory.create(sceneContext!));

    stage.on("mousedown touchstart", (e) => activeHandler?.onPointerDown?.(e));
    stage.on("mousemove touchmove", (e) => activeHandler?.onPointerMove?.(e));
    stage.on("mouseup touchend", (e) => activeHandler?.onPointerUp?.(e));

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
        syncRenderers();
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
    sceneReady = true;

    return () => {
      resizeObserver.disconnect();
      window.removeEventListener("keydown", onWindowKeyDown);
      activeHandler?.deactivate?.();
      activeHandler = null;
      sceneContext = null;
      sceneReady = false;
      for (const renderer of renderers) renderer.destroy();
      renderers = [];
      stage?.destroy();
      stage = null;
      imageLayer = null;
      konvaImage = null;
      loadedImg = null;
      placeholderShapes = [];
    };
  });

  // Swap the active tool handler whenever the widget's tool changes.
  $effect(() => {
    const toolId = storage.activeToolId;
    if (!sceneReady || !sceneContext) return;
    activeHandler?.deactivate?.();
    const tool = getTool2D(toolId) ?? getTool2D(DEFAULT_TOOL_2D)!;
    activeHandler = tool.createHandler(sceneContext);
    activeHandler.activate?.();
    if (containerEl) containerEl.style.cursor = tool.cursor ?? "default";
  });

  $effect(() => {
    void annotations.items.length;
    void annotations.selectedId;
    if (imageLoaded) syncRenderers();
  });

  const hasSelection = $derived(annotations.selectedId !== null);
  const widgetPending = $derived(
    new Set(
      manager.pendingMutations
        .filter((m) => m.widgetId === stableWidgetId && m.localAnnotationId)
        .map((m) => m.localAnnotationId as string),
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
    {#each TOOLS_2D as tool (tool.id)}
      <button
        type="button"
        onclick={() => (storage.activeToolId = storage.activeToolId === tool.id ? DEFAULT_TOOL_2D : tool.id)}
        title={tool.label}
        class="rounded p-1 text-muted-foreground hover:bg-accent hover:text-accent-foreground {storage.activeToolId === tool.id ? 'bg-accent text-accent-foreground' : ''}"
      >
        <tool.icon class="h-3.5 w-3.5" />
      </button>
    {/each}
    <span class="mx-1 h-4 w-px bg-border"></span>
    <button
      type="button"
      onclick={() => {
        const annotation = annotations.selected;
        if (!annotation || !sceneContext) return;
        deleteLocalAnnotation(annotation, annotations, sceneContext.mutations, stableWidgetId);
        syncRenderers();
      }}
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
