<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import Konva from "konva";
  import { untrack } from "svelte";
  import { Group, Image as KonvaImage, Layer, Rect, Stage } from "svelte-konva";

  import BBox2D from "./BBox2D.svelte";
  import BrushCursor from "./BrushCursor.svelte";
  import BrushMask from "./BrushMask.svelte";
  import CreatePolygon from "./CreatePolygon.svelte";
  import CreateRectangle from "./CreateRectangle.svelte";
  import Crosshair from "./Crosshair.svelte";
  import { clearParsedCache } from "./konvaMaskOps";
  import PolygonShape from "./PolygonShape.svelte";
  import ShowKeypoints from "./ShowKeypoint.svelte";
  import { FilterManager } from "./workers/filterManager";
  import type { FilterParams } from "./workers/filterWorker";
  import {
    ToolType,
    type Point2D,
    type PreviewShape,
    type SelectionTool,
    type ToolEvent,
  } from "$lib/tools";
  import {
    createInternalToolBridge,
    createToolFSMForSelection,
  } from "$lib/tools/canvasBridgeRuntime";
  import {
    brushDrawTool,
    getFallbackCanvasTool,
    handleToolShortcuts,
    isSupportedCanvasTool,
    panTool,
    polygonTool,
    rectangleTool,
    toggleBrushMode,
  } from "$lib/tools/canvasToolPolicy";
  import type { BBox, LoadedImagesPerView, Mask, Reference } from "$lib/types/dataset";
  import type { PolygonOutputMode } from "$lib/types/geometry";
  import {
    ShapeType,
    type CreatePolygonShape,
    type CreateRectangleShape,
    type ImageFilters,
    type KeypointAnnotation,
    type PolygonVertex,
    type SaveRectangleShape,
    type Shape,
  } from "$lib/types/shapeTypes";
  import type { ToolBridge } from "$lib/types/store";
  import { effectProbe } from "$lib/utils/effectProbe";
  import { equalizeHistogram } from "$lib/utils/equalizeHistogram";
  import { convertPointToSvg, runLengthEncode } from "$lib/utils/maskUtils";

  interface BrushSettings {
    brushRadius: number;
    lazyRadius: number;
    friction: number;
  }

  interface PolygonSavePayload {
    polygons?: PolygonVertex[][];
    points?: Point2D[];
    outputMode?: PolygonOutputMode;
  }

  function noopMerge(ann: unknown): void {
    void ann;
  }

  const DEFAULT_BRUSH_SETTINGS: BrushSettings = {
    brushRadius: 20,
    lazyRadius: 10,
    friction: 0.15,
  };

  const DEFAULT_FILTERS: ImageFilters = {
    brightness: 0,
    contrast: 0,
    equalizeHistogram: false,
    redRange: [0, 255],
    greenRange: [0, 255],
    blueRange: [0, 255],
    u16BitRange: [0, 65535],
  };

  interface BrushMaskRef {
    beginStroke(x: number, y: number): void;
    updateStroke(x: number, y: number): void;
    endStroke(): void;
    getMaskData(): Shape | null;
    clearCanvas(): void;
    destroy(): void;
  }
  interface Props {
    // Exports
    selectedItemId: string;
    masks: Mask[];
    bboxes: BBox[];
    keypoints?: KeypointAnnotation[];
    selectedTool: SelectionTool;
    newShape: Shape;
    imagesPerView: LoadedImagesPerView;
    colorScale: (value: string) => string;
    isVideo?: boolean;
    imageSmoothing?: boolean;
    isPlaybackActive?: boolean;
    merge?: (ann: unknown) => void;
    brushSettings?: BrushSettings;
    onSelectedToolChange?: (tool: SelectionTool) => void;
    onNewShapeChange?: (shape: Shape) => void;
    onBrushSettingsChange?: (settings: BrushSettings) => void;
    // New architecture (default behavior for the ongoing migration)
    useNewArchitecture?: boolean;
    toolBridge?: ToolBridge | undefined;
    // Image settings
    filters?: ImageFilters;
    canvasSize?: number;
  }

  let {
    selectedItemId,
    masks,
    bboxes,
    keypoints = [],
    selectedTool,
    newShape,
    imagesPerView,
    colorScale,
    isVideo = false,
    imageSmoothing = true,
    isPlaybackActive = false,
    merge = noopMerge,
    brushSettings = DEFAULT_BRUSH_SETTINGS,
    onSelectedToolChange,
    onNewShapeChange,
    onBrushSettingsChange,
    useNewArchitecture = true,
    toolBridge = undefined,
    filters = DEFAULT_FILTERS,
    canvasSize = 0,
  }: Props = $props();

  let isReady = $state(false);

  let prevSelectedTool: SelectionTool;
  let zoomFactor: Record<string, number> = $state({}); // {view_name: zoomFactor}

  let lastInputViewRef: Reference;
  let localDraftShape = $state<Shape | null>(null);

  // Runtime interaction flag toggled during wheel/drag to disable expensive draw options.
  let isViewportInteracting = $state(false);
  let interactionCooldownTimer: ReturnType<typeof setTimeout> | null = null;

  // Brush tool state
  let brushMaskRefs: Record<string, BrushMaskRef | undefined> = {};
  let activeBrushViewName: string | null = null;
  // Declarative crosshair & brush cursor state (replaces imperative Konva creation)
  let crosshairPosition = $state<Point2D | null>(null);
  let brushCursorState = $state<{
    x: number;
    y: number;
    radius: number;
    mode: "draw" | "erase";
  } | null>(null);
  let cursor = $state("default");
  let cursorFrameRequested = false;
  let queuedCursorPosition: Konva.Vector2d | null = null;
  // Layer-group references by view: split by background/static/active layers.
  let backgroundViewRefs: Record<string, { node: Konva.Group } | undefined> = {};
  let staticViewRefs: Record<string, { node: Konva.Group } | undefined> = {};
  let activeViewRefs: Record<string, { node: Konva.Group } | undefined> = {};
  let imageRefs: Record<string, Konva.Image> = {};

  // Web Worker-based filter manager (off-thread filter computation)
  let filterManager: FilterManager | null = null;

  // Reusable temp canvas for filter application (avoids per-call allocation)
  let filterTempCanvas: HTMLCanvasElement | null = null;
  let filterTempCtx: CanvasRenderingContext2D | null = null;

  let bboxEditable = $state(false);
  let rectangleSavePending = false;
  let internalToolBridge: ToolBridge | undefined = $state();
  let activeToolBridge: ToolBridge | undefined = $state();

  function clearRectangleTransformer() {
    bboxEditable = false;
  }

  function beginViewportInteraction() {
    if (interactionCooldownTimer) {
      clearTimeout(interactionCooldownTimer);
      interactionCooldownTimer = null;
    }
    isViewportInteracting = true;
  }

  function endViewportInteraction() {
    if (interactionCooldownTimer) {
      clearTimeout(interactionCooldownTimer);
    }
    interactionCooldownTimer = setTimeout(() => {
      isViewportInteracting = false;
      interactionCooldownTimer = null;
    }, 120);
  }

  let draftOrSavingShape = $derived.by<Shape | null>(() => {
    if (localDraftShape) return localDraftShape;
    if (
      newShape.status === "saving" &&
      (newShape.type === ShapeType.bbox ||
        newShape.type === ShapeType.polygon ||
        newShape.type === ShapeType.mask)
    ) {
      return newShape;
    }
    return null;
  });

  function toPolygonPoints(points: ReadonlyArray<PolygonVertex | Point2D>): PolygonVertex[] {
    return points.map((point, index) => ({
      x: point.x,
      y: point.y,
      id: "id" in point ? point.id : index,
    }));
  }

  function toClosedPolygonPoints(
    polygons: ReadonlyArray<ReadonlyArray<PolygonVertex | Point2D>>,
  ): PolygonVertex[][] {
    return polygons.map((polygon) => toPolygonPoints(polygon));
  }

  function getSourcePolygons(payload: PolygonSavePayload): Array<Array<PolygonVertex | Point2D>> {
    if (Array.isArray(payload.polygons) && payload.polygons.length > 0) {
      return payload.polygons;
    }

    if (Array.isArray(payload.points) && payload.points.length > 0) {
      return [payload.points.map((point) => ({ x: point.x, y: point.y }))];
    }

    return [];
  }

  function syncToolPreview(preview: PreviewShape | null) {
    if (rectangleSavePending) {
      rectangleSavePending = false;
      return;
    }
    const viewRef = lastInputViewRef;
    if (!viewRef) {
      localDraftShape = null;
      clearRectangleTransformer();
      return;
    }

    if (preview?.type === "polygon") {
      localDraftShape = {
        status: "creating",
        type: ShapeType.polygon,
        viewRef,
        phase: preview.phase,
        closedPolygons: toClosedPolygonPoints(preview.closedPolygons),
        points: toPolygonPoints(preview.points),
        current: preview.current,
        hoveredEdge: preview.hoveredEdge ?? null,
        outputMode: selectedTool?.type === ToolType.Polygon ? selectedTool.outputMode : "polygon",
      } as CreatePolygonShape;
      if (bboxEditable) {
        clearRectangleTransformer();
      }
      return;
    }

    if (preview?.type !== "rectangle") {
      localDraftShape = null;
      clearRectangleTransformer();
      return;
    }

    localDraftShape = {
      status: "creating",
      type: ShapeType.bbox,
      x: preview.origin.x,
      y: preview.origin.y,
      width: preview.current.x - preview.origin.x,
      height: preview.current.y - preview.origin.y,
      viewRef,
    };

    if (preview.editable) {
      bboxEditable = true;
    } else {
      if (bboxEditable) {
        clearRectangleTransformer();
      }
    }
  }

  function handleRectangleRequestSave(geometry: unknown) {
    const geo = geometry as { x: number; y: number; width: number; height: number };

    // Prefer the current local draft geometry (updated by Transformer/drag) over FSM's stale geometry
    let finalGeo = geo;
    if (localDraftShape?.status === "creating" && localDraftShape.type === ShapeType.bbox) {
      const shape = localDraftShape;
      const w = shape.width < 0 ? -shape.width : shape.width;
      const h = shape.height < 0 ? -shape.height : shape.height;
      const x = shape.width < 0 ? shape.x + shape.width : shape.x;
      const y = shape.height < 0 ? shape.y + shape.height : shape.y;
      finalGeo = { x, y, width: w, height: h };
    }

    localDraftShape = null;
    clearRectangleTransformer();

    const viewRef = lastInputViewRef;
    if (viewRef) {
      const currentImage = getCurrentImage(viewRef.name);
      if (!currentImage) return;
      rectangleSavePending = true;
      onNewShapeChange?.({
        status: "saving",
        attrs: {
          x: finalGeo.x,
          y: finalGeo.y,
          width: finalGeo.width,
          height: finalGeo.height,
        },
        type: ShapeType.bbox,
        viewRef,
        itemId: selectedItemId,
        imageWidth: currentImage.width,
        imageHeight: currentImage.height,
      });
    }
  }

  function handlePolygonRequestSave(geometry: unknown): void {
    const payload = geometry as PolygonSavePayload;
    const sourcePolygons = getSourcePolygons(payload);
    if (sourcePolygons.length === 0) return;

    const viewRef = lastInputViewRef;
    if (!viewRef) return;

    const currentImage = getCurrentImage(viewRef.name);
    if (!currentImage) return;
    const polygonMode: PolygonOutputMode = payload.outputMode ?? "polygon";
    const polygonPoints = sourcePolygons
      .map((polygon) =>
        polygon.map((point, id) => ({
          x: polygonMode === "mask" ? Math.round(point.x) : point.x,
          y: polygonMode === "mask" ? Math.round(point.y) : point.y,
          id: "id" in point ? point.id : id,
        })),
      )
      .filter((polygon) => polygon.length >= 3);
    if (polygonPoints.length === 0) return;

    const polygonSvg = polygonPoints.map((polygon) => convertPointToSvg(polygon));
    localDraftShape = null;
    cleanupPolygonPreviewListeners();

    if (polygonMode === "mask") {
      const counts = runLengthEncode(polygonSvg, currentImage.width, currentImage.height);
      onNewShapeChange?.({
        status: "saving",
        type: ShapeType.mask,
        masksImageSVG: polygonSvg,
        rle: {
          counts,
          size: [currentImage.height, currentImage.width],
        },
        viewRef,
        itemId: selectedItemId,
        imageWidth: currentImage.width,
        imageHeight: currentImage.height,
        polygonMode,
        polygonPoints,
      });
      return;
    }

    onNewShapeChange?.({
      status: "saving",
      type: ShapeType.polygon,
      masksImageSVG: polygonSvg,
      viewRef,
      itemId: selectedItemId,
      imageWidth: currentImage.width,
      imageHeight: currentImage.height,
      polygonMode,
      polygonPoints,
    });
  }

  function handleToolRequestSave(
    shapeType: "bbox" | "polygon" | "mask" | "keypoints",
    geometry: unknown,
  ) {
    if (shapeType === "bbox") {
      handleRectangleRequestSave(geometry);
      return;
    }

    if (shapeType === "polygon") {
      handlePolygonRequestSave(geometry);
    }
  }

  function dispatchPolygonToolEvent(event: ToolEvent) {
    activeToolBridge?.dispatchEvent(event);
  }

  // References to HTML Elements
  let stageContainer: HTMLElement = $state();

  // References to Konva Elements — bind:this on svelte-konva v1.0.1 gives { node: Konva.X }
  let stageComponent: { node: Konva.Stage } | undefined = $state();
  let stage: Konva.Stage | undefined = $derived(stageComponent?.node);

  // Stage size driven by $state (ResizeObserver updates these)
  let stageWidth = $state(512);
  let stageHeight = $state(780);

  // Multiview image grid
  let gridSize = {
    rows: 0,
    cols: 0,
  };

  let currentId: string;

  // Dynamically set the canvas stage size
  const resizeObserver = new ResizeObserver((entries) => {
    for (const entry of entries) {
      if (entry.target !== stageContainer) continue;

      let width: number;
      let height: number;

      if (entry.contentBoxSize) {
        // Firefox implements `contentBoxSize` as a single ResizeObserverSize, rather than an array
        const contentBoxSize: ResizeObserverSize = (
          Array.isArray(entry.contentBoxSize) ? entry.contentBoxSize[0] : entry.contentBoxSize
        ) as ResizeObserverSize;
        width = contentBoxSize.inlineSize;
        height = contentBoxSize.blockSize;
      } else {
        width = entry.contentRect.width;
        height = entry.contentRect.height;
      }

      // Check if the dimensions have actually changed to avoid unnecessary redraws
      if (stageWidth !== width || stageHeight !== height) {
        stageWidth = width;
        stageHeight = height;
        if (isReady) {
          for (const view_name of Object.keys(imagesPerView)) {
            scaleView(view_name);
          }
        }
        stage?.batchDraw();
      }
    }
  });

  // ********** INIT ********** //

  $effect(() => {
    if (useNewArchitecture && !toolBridge) {
      internalToolBridge = createInternalToolBridge(selectedItemId);
    }

    Object.keys(imagesPerView).forEach((view_name) => {
      zoomFactor[view_name] = 1;
    });

    // Initialize off-thread filter manager
    filterManager = new FilterManager((viewName, filteredCanvas) => {
      const image = getImageNode(viewName);
      if (image) {
        image.image(filteredCanvas);
        image.clearCache();
        image.getLayer()?.batchDraw();
      }
    });

    // Fire stage events observers
    resizeObserver.observe(stageContainer);

    return () => {
      resizeObserver.disconnect();
      const pendingFilterTimer = untrack(() => filterDebounceTimer);
      if (pendingFilterTimer) {
        clearTimeout(pendingFilterTimer);
      }
      if (interactionCooldownTimer) {
        clearTimeout(interactionCooldownTimer);
        interactionCooldownTimer = null;
      }
      clearAnnotationAndInputs();
      filterManager?.destroy();
      filterManager = null;
    };
  });

  // React to filter changes (debounced, skip for video)
  let filterDebounceTimer: ReturnType<typeof setTimeout>;

  let scaleOnFirstLoad: Record<string, boolean> = {};
  let viewReady: Record<string, boolean> = {};
  let loadCycle = 0;

  function resetViewFlags(viewNames: string[]): void {
    scaleOnFirstLoad = {};
    viewReady = {};
    for (const view_name of viewNames) {
      //we need a first scaleView for image only. If video, the scale is done elsewhere
      scaleOnFirstLoad[view_name] = !isVideo;
      viewReady[view_name] = false;
    }
  }

  type ViewGroupKind = "background" | "static" | "active";

  function getViewGroup(view_name: string, kind: ViewGroupKind): Konva.Group | undefined {
    if (kind === "background") {
      return backgroundViewRefs[view_name]?.node ?? stage?.findOne(`#bg-${view_name}`);
    }
    if (kind === "static") {
      return staticViewRefs[view_name]?.node ?? stage?.findOne(`#static-${view_name}`);
    }
    return activeViewRefs[view_name]?.node ?? stage?.findOne(`#active-${view_name}`);
  }

  /** Main interaction group (pointer coordinate system for tools). */
  function getViewLayer(view_name: string): Konva.Group | undefined {
    return getViewGroup(view_name, "active");
  }

  function forEachLinkedViewGroup(view_name: string, callback: (group: Konva.Group) => void) {
    const groups = [
      getViewGroup(view_name, "background"),
      getViewGroup(view_name, "static"),
      getViewGroup(view_name, "active"),
    ];
    for (const group of groups) {
      if (group) callback(group);
    }
  }

  function syncLinkedViewGroupsFromActive(view_name: string) {
    const active = getViewGroup(view_name, "active");
    if (!active) return;
    const x = active.x();
    const y = active.y();
    const scaleX = active.scaleX();
    const scaleY = active.scaleY();
    forEachLinkedViewGroup(view_name, (group) => {
      if (group === active) return;
      group.position({ x, y });
      group.scale({ x: scaleX, y: scaleY });
    });
  }

  function applyViewTransform(
    view_name: string,
    transform: { x: number; y: number; scale: number },
  ) {
    forEachLinkedViewGroup(view_name, (group) => {
      group.scale({ x: transform.scale, y: transform.scale });
      group.position({ x: transform.x, y: transform.y });
    });
  }

  /** Get the image node for a view using cached ref (O(1)) with fallback. */
  function getImageNode(view_name: string): Konva.Image | undefined {
    return imageRefs[view_name] ?? stage?.findOne(`#image-${view_name}`);
  }

  /** Register an image ref when image loads. */
  function registerImageRef(view_name: string): void {
    // Called after image onload; find the image node in the now-populated layer
    const img: Konva.Image | undefined = stage?.findOne(`#image-${view_name}`);
    if (img) imageRefs[view_name] = img;
  }

  function getCurrentImage(view_name: string): HTMLImageElement | undefined {
    const viewImages = imagesPerView[view_name];
    if (!Array.isArray(viewImages) || viewImages.length === 0) return undefined;
    const latestViewImage = viewImages[viewImages.length - 1];
    return latestViewImage?.element;
  }

  function loadItem() {
    const thisLoadCycle = ++loadCycle;
    const keys = Object.keys(imagesPerView);
    const totalKeys = keys.length;

    if (totalKeys === 0) {
      isReady = false;
      currentId = selectedItemId;
      return;
    }

    // Calculate new grid size
    gridSize.cols = Math.ceil(Math.sqrt(totalKeys));
    gridSize.rows = Math.ceil(totalKeys / gridSize.cols);

    // Clear annotations in case a previous item was already loaded
    if (currentId) clearAnnotationAndInputs();
    clearParsedCache();

    // Reset flags for the new item
    isReady = false;
    resetViewFlags(keys);

    keys.forEach((view_name) => {
      const currentImage = getCurrentImage(view_name);
      if (!currentImage) {
        viewReady[view_name] = true;
        if (Object.values(viewReady).every(Boolean)) {
          isReady = true;
        }
        console.warn(
          `[Canvas2D] Missing current image for view '${view_name}' on item '${selectedItemId}'.`,
        );
        return;
      }

      const onImageReady = () => {
        if (thisLoadCycle !== loadCycle) return;
        registerImageRef(view_name);
        if (scaleOnFirstLoad[view_name]) {
          if (scaleView(view_name)) {
            scaleOnFirstLoad[view_name] = false;
          } else {
            requestAnimationFrame(() => {
              if (thisLoadCycle !== loadCycle) return;
              if (scaleOnFirstLoad[view_name] && scaleView(view_name)) {
                scaleOnFirstLoad[view_name] = false;
                stage?.batchDraw();
              }
            });
          }
        }
        //scaleElements(view_name);
        viewReady[view_name] = true;
        if (Object.values(viewReady).every(Boolean)) {
          isReady = true;
        }
        if (!isVideo) cacheImage();
      };
      const onImageError = () => {
        if (thisLoadCycle !== loadCycle) return;
        const failedUrl = currentImage.currentSrc || currentImage.src || "<unknown>";
        console.warn(
          `[Canvas2D] Failed to load image for view '${view_name}' on item '${selectedItemId}': ${failedUrl}`,
        );
        viewReady[view_name] = true;
        if (Object.values(viewReady).every(Boolean)) {
          isReady = true;
        }
      };

      currentImage.onload = onImageReady;
      currentImage.onerror = onImageError;
      // Handle already-loaded images (e.g., from browser cache)
      if (currentImage.complete && currentImage.naturalWidth > 0) {
        onImageReady();
      } else if (currentImage.complete && currentImage.naturalWidth === 0) {
        onImageError();
      }
    });

    currentId = selectedItemId;
  }

  function scaleView(view_name: string): boolean {
    const hasAnyLayer =
      !!getViewGroup(view_name, "background") ||
      !!getViewGroup(view_name, "static") ||
      !!getViewGroup(view_name, "active");
    if (!hasAnyLayer) {
      return false;
    }
    // Calculate max dims for every image in the grid
    const maxWidth = stageContainer.getBoundingClientRect().width / gridSize.cols;
    const maxHeight = stageContainer.getBoundingClientRect().height / gridSize.rows;

    // Get view index
    const keys = Object.keys(imagesPerView);
    const i = keys.findIndex((view) => view === view_name);

    // Calculate view position in grid
    const gridPosition = {
      x: i % gridSize.cols,
      y: Math.floor(i / gridSize.cols),
    };

    // Fit stage
    const currentImage = getCurrentImage(view_name);
    if (!currentImage) {
      return false;
    }
    const scaleByHeight = maxHeight / currentImage.height;
    const scaleByWidth = maxWidth / currentImage.width;
    const scale = Math.min(scaleByWidth, scaleByHeight);

    // Set zoom factor for this view.
    zoomFactor[view_name] = scale;

    // Center view
    const offsetX = (maxWidth - currentImage.width * scale) / 2 + gridPosition.x * maxWidth;
    const offsetY = (maxHeight - currentImage.height * scale) / 2 + gridPosition.y * maxHeight;
    applyViewTransform(view_name, { x: offsetX, y: offsetY, scale });
    return true;
  }

  function cacheImage(): void {
    if (!stage) return;

    for (const view_name of Object.keys(imagesPerView)) {
      const image = getImageNode(view_name);
      if (!image || image.width() === 0 || image.height() === 0) continue;
      image.cache();
    }
  }

  function adjustChannels(imageData: ImageData): void {
    const { data } = imageData;

    const redMin = filters.redRange[0];
    const redMax = filters.redRange[1];
    const greenMin = filters.greenRange[0];
    const greenMax = filters.greenRange[1];
    const blueMin = filters.blueRange[0];
    const blueMax = filters.blueRange[1];

    for (let i = 0; i < data.length; i += 4) {
      const red = data[i];
      const green = data[i + 1];
      const blue = data[i + 2];

      if (
        red < redMin ||
        red > redMax ||
        green < greenMin ||
        green > greenMax ||
        blue < blueMin ||
        blue > blueMax
      ) {
        data[i] = 0; // Red channel
        data[i + 1] = 0; // Green channel
        data[i + 2] = 0; // Blue channel
      }
    }
  }

  function applyFilters(): void {
    if (!stage) return;

    const workerFilters: FilterParams = {
      brightness: filters.brightness,
      contrast: filters.contrast,
      redRange: [...filters.redRange] as [number, number],
      greenRange: [...filters.greenRange] as [number, number],
      blueRange: [...filters.blueRange] as [number, number],
      equalizeHistogram: filters.equalizeHistogram,
    };

    for (const view_name of Object.keys(imagesPerView)) {
      const image = getImageNode(view_name);
      if (!image) continue;

      // Try off-thread path via Web Worker
      if (filterManager) {
        // We need the original (uncached) image to get source pixel data.
        // Use the source canvas/image element from imagesPerView.
        const sourceElement = getCurrentImage(view_name);
        if (sourceElement) {
          // Reuse a single temp canvas for filter source data
          if (!filterTempCanvas) {
            filterTempCanvas = document.createElement("canvas");
            filterTempCtx = filterTempCanvas.getContext("2d");
          }
          filterTempCanvas.width = sourceElement.width;
          filterTempCanvas.height = sourceElement.height;
          if (filterTempCtx) {
            filterTempCtx.drawImage(sourceElement, 0, 0);
            filterManager.applyFilters(view_name, filterTempCanvas, workerFilters);
            continue;
          }
        }
      }

      // Fallback: synchronous Konva filter pipeline
      const filtersList = [Konva.Filters.Brighten, Konva.Filters.Contrast, adjustChannels];
      if (filters.equalizeHistogram) filtersList.push(equalizeHistogram);

      image.filters(filtersList);
      image.brightness(filters.brightness);
      image.contrast(filters.contrast);
    }
  }

  // ********** TOOLS ********** //

  function handleChangeTool() {
    endViewportInteraction();
    if (selectedTool?.type === ToolType.Pan) {
      crosshairPosition = null;
      brushCursorState = null;
      cleanupPolygonPreviewListeners();
      cursor = panTool.cursor;
      return;
    }

    if (selectedTool?.type === ToolType.Rectangle) {
      cleanupPolygonPreviewListeners();
      brushCursorState = null;
      cursor = rectangleTool.cursor;
      return;
    }

    if (selectedTool?.type === ToolType.Polygon) {
      brushCursorState = null;
      cursor = polygonTool.cursor;
      return;
    }

    if (selectedTool?.type === ToolType.Brush) {
      cleanupPolygonPreviewListeners();
      crosshairPosition = null;
      cursor = "none";
      return;
    }

    cleanupPolygonPreviewListeners();
    crosshairPosition = null;
    brushCursorState = null;
    cursor = "default";
  }

  function updateBrushCursor(mousePos: Konva.Vector2d) {
    if (selectedTool?.type !== ToolType.Brush) return;
    const mode = selectedTool.mode;
    brushCursorState = {
      x: mousePos.x,
      y: mousePos.y,
      radius: brushSettings.brushRadius,
      mode,
    };
  }

  function cleanupBrushCursor() {
    brushCursorState = null;
  }

  // Keep brush cursor in sync when brushSettings/mode change (Q/E/X keys)
  $effect(() => {
    const radius = brushSettings.brushRadius;
    const mode = selectedTool?.type === ToolType.Brush ? selectedTool.mode : null;
    const current = untrack(() => brushCursorState);
    if (current && mode) {
      brushCursorState = { ...current, radius, mode };
    }
  });

  function handleBrushPointerDown(viewRef: Reference) {
    const viewLayer = getViewLayer(viewRef.name);
    if (!viewLayer) return;
    const pos = viewLayer.getRelativePointerPosition();
    if (!pos) return;

    beginViewportInteraction();
    activeBrushViewName = viewRef.name;
    const brushRef = brushMaskRefs[viewRef.name];
    if (brushRef) {
      brushRef.beginStroke(pos.x, pos.y);
    }
  }

  function handleBrushPointerMove(view_name: string) {
    const viewLayer = getViewLayer(view_name);
    if (!viewLayer) return;
    const pos = viewLayer.getRelativePointerPosition();
    if (!pos) return;

    const brushRef = brushMaskRefs[view_name];
    if (brushRef) {
      brushRef.updateStroke(pos.x, pos.y);
    }
  }

  function handleBrushPointerUp(view_name: string) {
    activeBrushViewName = null;
    const brushCanvas = brushMaskRefs[view_name];
    if (brushCanvas) {
      brushCanvas.endStroke();
    }
    endViewportInteraction();
  }

  function saveBrushMask(view_name: string) {
    const brushCanvas = brushMaskRefs[view_name];
    if (brushCanvas) {
      const maskData = brushCanvas.getMaskData();
      if (maskData) {
        onNewShapeChange?.(maskData);
      }
    }
  }

  function cleanupAllBrushCanvases() {
    for (const key of Object.keys(brushMaskRefs)) {
      const brushRef = brushMaskRefs[key];
      if (brushRef) {
        brushRef.destroy();
      }
      delete brushMaskRefs[key];
    }
    cleanupBrushCursor();
  }

  function cleanupPolygonPreviewListeners() {
    for (const view_name of Object.keys(imagesPerView)) {
      const viewLayer = getViewLayer(view_name);
      if (viewLayer) {
        viewLayer.off("pointermove.polygon");
      }
    }
  }

  // ********** CROSSHAIR TOOL ********** //

  function updateCrosshairState(mousePos: Konva.Vector2d) {
    crosshairPosition = { x: mousePos.x, y: mousePos.y };
  }

  function flushCursorOverlayState() {
    cursorFrameRequested = false;
    const position = queuedCursorPosition;
    if (!position) return;

    if (
      selectedTool?.type === ToolType.Rectangle ||
      selectedTool?.type === ToolType.Polygon ||
      selectedTool?.type === ToolType.Brush
    ) {
      updateCrosshairState(position);
    } else {
      crosshairPosition = null;
    }

    if (selectedTool?.type === ToolType.Brush) {
      updateBrushCursor(position);
      if (activeBrushViewName) {
        handleBrushPointerMove(activeBrushViewName);
      }
    } else {
      brushCursorState = null;
    }
  }

  function clearAnnotationAndInputs() {
    if (selectedTool?.postProcessor) {
      selectedTool.postProcessor.reset();
    }
    if (selectedTool) {
      cursor = selectedTool.cursor;
    }
    // Declarative cleanup — just reset state, Svelte will remove the components
    localDraftShape = null;
    isViewportInteracting = false;
    crosshairPosition = null;
    queuedCursorPosition = null;
    cursorFrameRequested = false;
    cleanupBrushCursor();
    cleanupPolygonPreviewListeners();
    // Only clear brush canvases after the user confirms (shouldReset) or
    // when leaving the brush tool — NOT while the save form is open.
    if (newShape.status !== "saving") {
      if (
        selectedTool?.type !== ToolType.Brush ||
        ("shouldReset" in newShape && newShape.shouldReset)
      ) {
        for (const key of Object.keys(brushMaskRefs)) {
          brushMaskRefs[key]?.clearCanvas();
        }
      }
    }
  }

  // ********** MOUSE EVENTS ********** //

  function handleMouseMoveStage() {
    if (!stage) return;
    const position = stage.getRelativePointerPosition();
    if (!position) return;
    queuedCursorPosition = position;
    if (!cursorFrameRequested) {
      cursorFrameRequested = true;
      requestAnimationFrame(flushCursorOverlayState);
    }
  }

  function handleMouseEnterStage() {
    // Declarative: crosshair/brushCursor are conditionally rendered,
    // they become visible via their $state conditions
  }

  function handleMouseLeaveStage() {
    // Hide crosshair and brush cursor when mouse leaves stage
    crosshairPosition = null;
    brushCursorState = null;
    queuedCursorPosition = null;
    cursorFrameRequested = false;
    // End any ongoing brush stroke when mouse leaves
    if (selectedTool?.type === ToolType.Brush && activeBrushViewName) {
      handleBrushPointerUp(activeBrushViewName);
    }
    for (const view_name of Object.keys(imagesPerView)) {
      const viewLayer = getViewLayer(view_name);
      if (viewLayer) {
        viewLayer.off("pointermove.rectangle");
        viewLayer.off("pointerup.rectangle");
      }
    }
    endViewportInteraction();
  }

  function handlePointerUpOnImage(viewRef: Reference) {
    if (selectedTool?.type === ToolType.Brush) {
      handleBrushPointerUp(viewRef.name);
    }
  }

  function handleDoubleClickOnImage(view_name: string) {
    // Keep all three per-view groups stacked together when prioritizing a view.
    const backgroundGroup = getViewGroup(view_name, "background");
    const staticGroup = getViewGroup(view_name, "static");
    const activeGroup = getViewGroup(view_name, "active");
    if (backgroundGroup?.getParent()) backgroundGroup.moveToTop();
    if (staticGroup?.getParent()) staticGroup.moveToTop();
    if (activeGroup?.getParent()) activeGroup.moveToTop();
  }

  function handleSelectBBox(bbox: BBox) {
    if (bbox.ui.displayControl.highlighted !== "self") {
      onNewShapeChange?.({
        status: "editing",
        shapeId: bbox.id,
        top_entity_id: (bbox.ui.top_entities ?? [])[0]?.id ?? bbox.data.entity_id,
        viewRef: { name: bbox.data.view_name, id: bbox.data.frame_id },
        highlighted: "self",
        type: ShapeType.none,
      });
    }
    merge?.(bbox);
  }

  function handleClickOnImage(event: PointerEvent, viewRef: Reference) {
    const viewLayer = getViewLayer(viewRef.name);
    if (!viewLayer) return;
    if (selectedTool?.type === ToolType.Pan && event.button !== 1) {
      return;
    }
    const interactionShape = localDraftShape ?? newShape;

    if (
      (interactionShape.status === "none" || interactionShape.status === "editing") &&
      selectedTool?.type !== ToolType.Pan &&
      selectedTool?.type !== ToolType.Brush &&
      selectedTool?.type !== ToolType.Polygon
    ) {
      onNewShapeChange?.({
        status: "editing",
        viewRef,
        type: "none",
        shapeId: null,
        highlighted: "all",
      });
    }
    if (event.button === 1 && selectedTool?.type !== ToolType.Pan) {
      // Middle-button: temporary pan from any tool
      beginViewportInteraction();
      viewLayer.draggable(true);
      viewLayer.startDrag();
      const onDragEnd = () => {
        if (selectedTool?.type !== ToolType.Pan) {
          viewLayer.draggable(false);
        }
        viewLayer.off("dragend.temp-pan", onDragEnd);
      };
      viewLayer.on("dragend.temp-pan", onDragEnd);
      return;
    } else if (selectedTool?.type === ToolType.Brush) {
      handleBrushPointerDown(viewRef);
    } else if (selectedTool?.type === ToolType.Rectangle && !bboxEditable) {
      const bridge = activeToolBridge;
      if (!bridge) return;

      lastInputViewRef = viewRef;
      bridge.setCanvasContext(viewRef.name, stageWidth, stageHeight);
      const pos = viewLayer.getRelativePointerPosition();
      if (!pos) return;
      beginViewportInteraction();
      bridge.dispatchEvent({
        type: "pointerDown",
        position: { x: pos.x, y: pos.y },
        button: event.button,
      });
      viewLayer.off("pointermove.rectangle");
      viewLayer.off("pointerup.rectangle");
      viewLayer.on("pointermove.rectangle", () => {
        const movePos = viewLayer.getRelativePointerPosition();
        if (!movePos) return;
        bridge.dispatchEvent({
          type: "pointerMove",
          position: { x: movePos.x, y: movePos.y },
        });
      });
      viewLayer.on("pointerup.rectangle", () => {
        const upPos = viewLayer.getRelativePointerPosition();
        if (!upPos) return;
        bridge.dispatchEvent({
          type: "pointerUp",
          position: { x: upPos.x, y: upPos.y },
        });
        endViewportInteraction();
        viewLayer.off("pointermove.rectangle");
        viewLayer.off("pointerup.rectangle");
      });
    } else if (selectedTool?.type === ToolType.Polygon) {
      if (event.button !== 0) return;
      const bridge = activeToolBridge;
      if (!bridge) return;

      lastInputViewRef = viewRef;
      bridge.setCanvasContext(viewRef.name, stageWidth, stageHeight);
      const pos = viewLayer.getRelativePointerPosition();
      if (!pos) return;

      bridge.dispatchEvent({
        type: "pointerDown",
        position: { x: pos.x, y: pos.y },
        button: event.button,
      });

      viewLayer.off("pointermove.polygon");
      viewLayer.on("pointermove.polygon", () => {
        const movePos = viewLayer.getRelativePointerPosition();
        if (!movePos) return;
        bridge.dispatchEvent({
          type: "pointerMove",
          position: { x: movePos.x, y: movePos.y },
        });
      });
    }
  }

  function zoom(stageNode: Konva.Stage, direction: number, view_name: string): number {
    // Defines zoom speed
    const zoomScale = 1.05;

    const viewLayer = getViewLayer(view_name);
    if (!viewLayer) return 1;

    // Get old scaling
    const oldScale = viewLayer.scaleX();

    // Get mouse position
    const pointer = stageNode.getRelativePointerPosition();
    const mousePointTo = {
      x: (pointer.x - viewLayer.x()) / oldScale,
      y: (pointer.y - viewLayer.y()) / oldScale,
    };

    // Calculate new scaling
    const newScale = direction > 0 ? oldScale * zoomScale : oldScale / zoomScale;

    // Calculate new position
    const newPos = {
      x: pointer.x - mousePointTo.x * newScale,
      y: pointer.y - mousePointTo.y * newScale,
    };

    // Change scaling and position
    applyViewTransform(view_name, {
      x: newPos.x,
      y: newPos.y,
      scale: newScale,
    });

    return newScale;
  }

  function handleWheelOnImage(event: WheelEvent, view_name: string) {
    // Prevent default scrolling
    event.preventDefault();
    if (!stage) return;
    beginViewportInteraction();

    // Get zoom direction
    let direction = event.deltaY < 0 ? 1 : -1;

    // Revert direction for trackpad
    if (event.ctrlKey) direction = -direction;

    // Zoom
    zoomFactor[view_name] = zoom(stage, direction, view_name);
    stage.batchDraw();
    endViewportInteraction();
  }

  function asRectangleShape(shape: Shape): CreateRectangleShape | SaveRectangleShape {
    return shape as CreateRectangleShape | SaveRectangleShape;
  }

  let bboxesByView = $derived.by(() => {
    const grouped: Record<string, BBox[]> = {};
    for (const bbox of bboxes) {
      const key = bbox.data.view_name;
      if (!grouped[key]) grouped[key] = [];
      grouped[key].push(bbox);
    }
    return grouped;
  });

  let masksByView = $derived.by(() => {
    const grouped: Record<string, Mask[]> = {};
    for (const mask of masks) {
      const key = mask.data.view_name;
      if (!grouped[key]) grouped[key] = [];
      grouped[key].push(mask);
    }
    return grouped;
  });

  let keypointsByView = $derived.by(() => {
    const grouped: Record<string, KeypointAnnotation[]> = {};
    for (const kpt of keypoints) {
      const key = kpt.viewRef?.name;
      if (!key) continue;
      if (!grouped[key]) grouped[key] = [];
      grouped[key].push(kpt);
    }
    return grouped;
  });

  let draftRectangle = $derived.by<CreateRectangleShape | SaveRectangleShape | null>(() => {
    const shape = draftOrSavingShape;
    if (!shape) return null;
    if (!("type" in shape) || shape.type !== ShapeType.bbox) return null;
    return asRectangleShape(shape);
  });

  let draftPolygon = $derived.by<Shape | null>(() => {
    const shape = draftOrSavingShape;
    if (!shape) return null;
    if (!("type" in shape)) return null;
    if (shape.type === ShapeType.polygon) return shape;
    if (shape.type === ShapeType.mask && "polygonMode" in shape) return shape;
    return null;
  });

  // Video/frame updates can replace many Konva nodes at once (images + overlays).
  // Force a single batched redraw on the next frame when frame identities change.
  $effect(() => {
    const stageNode = stage;
    if (!stageNode) return;
    for (const [view_name, images] of Object.entries(imagesPerView)) {
      void view_name;
      const latest = images[images.length - 1];
      void latest?.id;
    }
    for (const bbox of bboxes) {
      void bbox.id;
      void bbox.data.frame_id;
      void bbox.data.view_name;
    }
    for (const mask of masks) {
      void mask.id;
      void mask.data.frame_id;
      void mask.data.view_name;
      void mask.ui.svg?.length;
    }
    for (const kpt of keypoints) {
      void kpt.id;
      void kpt.viewRef?.id;
      void kpt.viewRef?.name;
    }
    requestAnimationFrame(() => stageNode.batchDraw());
  });

  // ********** KEY EVENTS ********** //

  function handleKeyDown(event: KeyboardEvent) {
    const activeElement = document.activeElement;
    if (
      activeElement instanceof HTMLInputElement ||
      activeElement instanceof HTMLTextAreaElement ||
      activeElement?.getAttribute("contenteditable") === "true"
    ) {
      return; // Ignore shortcut when typing text
    }

    if (event.key === "Escape") {
      const interactionShape = localDraftShape ?? newShape;
      const shouldKeepPolygonTool =
        selectedTool?.type === ToolType.Polygon &&
        interactionShape.status === "creating" &&
        interactionShape.type === ShapeType.polygon &&
        interactionShape.phase === "drawing" &&
        interactionShape.closedPolygons.length > 0;

      if (selectedTool?.type === ToolType.Rectangle || selectedTool?.type === ToolType.Polygon) {
        activeToolBridge?.dispatchEvent({ type: "cancel" });
      }

      if (shouldKeepPolygonTool) {
        return;
      }

      if (selectedTool?.type === ToolType.Brush) {
        cleanupAllBrushCanvases();
      }

      clearRectangleTransformer();
      localDraftShape = null;
      onNewShapeChange?.({ status: "none", shouldReset: true });
      onSelectedToolChange?.(panTool);
      return;
    }

    const shortcutHandled = handleToolShortcuts(event, selectedTool, {
      selectPan: () => onSelectedToolChange?.(panTool),
      selectRectangle: () => onSelectedToolChange?.(rectangleTool),
      selectPolygon: () => onSelectedToolChange?.(polygonTool),
      selectBrushDraw: () => onSelectedToolChange?.(brushDrawTool),
      toggleBrushMode: () => {
        if (selectedTool?.type === ToolType.Brush) {
          onSelectedToolChange?.(toggleBrushMode(selectedTool));
        }
      },
      adjustBrushRadius: (delta) => {
        onBrushSettingsChange?.({
          ...brushSettings,
          brushRadius: Math.max(1, Math.min(100, brushSettings.brushRadius + delta)),
        });
      },
      saveBrushMask: () => {
        for (const view_name of Object.keys(imagesPerView)) {
          saveBrushMask(view_name);
        }
      },
    });

    if (shortcutHandled && event.key !== "Enter") {
      return;
    }

    if (
      (event.key === "Enter" || event.key === "Backspace") &&
      (selectedTool?.type === ToolType.Rectangle || selectedTool?.type === ToolType.Polygon)
    ) {
      activeToolBridge?.dispatchEvent({
        type: "keyDown",
        key: event.key,
        modifiers: {
          shift: event.shiftKey,
          ctrl: event.ctrlKey,
          alt: event.altKey,
          meta: event.metaKey,
        },
      });
      return;
    }
  }
  $effect(() => {
    effectProbe("Canvas2D.toolFallback");
    const currentTool = selectedTool;
    const shouldFallback = useNewArchitecture && currentTool && !isSupportedCanvasTool(currentTool);
    if (shouldFallback) {
      const fallback = getFallbackCanvasTool();
      if (currentTool !== fallback) {
        onSelectedToolChange?.(fallback);
      }
    }
  });
  // True for active painting flows in the reduced Pan/Rectangle/Brush architecture.
  let isActivePaintingTool = $derived(selectedTool?.type === ToolType.Brush);
  $effect(() => {
    effectProbe("Canvas2D.shouldReset");
    const shapeStatus = newShape.status;
    const shouldReset = "shouldReset" in newShape ? newShape.shouldReset : false;
    if (shapeStatus === "none" && shouldReset) {
      untrack(() => {
        clearAnnotationAndInputs();
      });
      onNewShapeChange?.({ status: "none" });
    }
  });
  $effect(() => {
    effectProbe("Canvas2D.toolCleanup");
    const currentTool = selectedTool;
    const previousTool = prevSelectedTool;
    const shapeStatus = newShape.status;
    const shouldReset = "shouldReset" in newShape ? newShape.shouldReset : false;

    const switchingBrushMode =
      previousTool?.type === ToolType.Brush && currentTool?.type === ToolType.Brush;

    if (!switchingBrushMode || (shapeStatus === "none" && shouldReset)) {
      untrack(() => {
        clearAnnotationAndInputs();
      });
    }
    prevSelectedTool = currentTool;
  });
  let lastAppliedCanvasSize: number | null = null;
  $effect(() => {
    effectProbe("Canvas2D.canvasSize");
    if (!isReady || !canvasSize) return;
    if (lastAppliedCanvasSize === canvasSize) return;
    for (const view_name of Object.keys(imagesPerView)) {
      scaleView(view_name);
    }
    lastAppliedCanvasSize = canvasSize;
  });
  $effect(() => {
    effectProbe("Canvas2D.toolBridge");
    const bridge = useNewArchitecture ? (toolBridge ?? internalToolBridge) : undefined;
    const currentBridge = untrack(() => activeToolBridge);
    if (bridge !== currentBridge) {
      activeToolBridge = bridge;
      if (bridge) {
        bridge.onRequestSave(handleToolRequestSave);
      }
    }
  });
  $effect(() => {
    effectProbe("Canvas2D.previewSync");
    const bridge = activeToolBridge;
    if (!bridge) {
      localDraftShape = null;
      return;
    }
    const preview = bridge.preview.value;
    untrack(() => syncToolPreview(preview));
  });
  $effect(() => {
    effectProbe("Canvas2D.fsmSwitch");
    if (useNewArchitecture && activeToolBridge && selectedTool) {
      const fsm = createToolFSMForSelection(selectedTool);
      if (fsm) {
        activeToolBridge.switchTool(fsm);
      }
    }
  });
  // --- Targeted reactive statements (replaces monolithic afterUpdate) ---

  // React to item changes
  $effect(() => {
    effectProbe("Canvas2D.itemChange");
    if (selectedItemId && currentId !== selectedItemId) {
      loadItem();
    }
  });
  // React to tool changes
  $effect(() => {
    effectProbe("Canvas2D.toolChangeHandler");
    const currentTool = selectedTool;
    const currentStage = untrack(() => stage);
    if (currentStage && currentTool) {
      untrack(() => {
        handleChangeTool();
      });
    } else if (currentStage && !currentTool) {
      cursor = "default";
    }
  });
  // Reactively set viewLayer.draggable based on tool selection.
  // This ensures Konva's internal mousedown.konva listener is registered
  // BEFORE any click, eliminating the timing race that caused drag unresponsiveness.
  $effect(() => {
    const isPan = selectedTool?.type === ToolType.Pan;
    const viewNames = Object.keys(imagesPerView);
    untrack(() => {
      for (const name of viewNames) {
        const viewLayer = getViewLayer(name);
        if (viewLayer) {
          viewLayer.draggable(isPan);
          viewLayer.dragDistance(0);
        }
      }
    });
  });
  // Transformer is now declarative inside BBox2D.svelte — no manual attachment needed
  $effect(() => {
    effectProbe("Canvas2D.filter");
    if (!isVideo && stage && filters) {
      const previousTimer = untrack(() => filterDebounceTimer);
      if (previousTimer) {
        clearTimeout(previousTimer);
      }
      filterDebounceTimer = setTimeout(() => applyFilters(), 50);
    }
  });
  // Brush cursor is now declarative — BrushCursor.svelte renders from brushCursorState
</script>

<div
  class={`h-full bg-canvas transition-opacity duration-300 delay-100 relative ${isReady ? "" : "opacity-0"}`}
  bind:this={stageContainer}
>
  <Stage
    bind:this={stageComponent}
    width={stageWidth}
    height={stageHeight}
    name="konva"
    id="stage"
    divWrapperProps={{ style: `cursor: ${cursor}` }}
    onmousemove={handleMouseMoveStage}
    onmouseenter={handleMouseEnterStage}
    onmouseleave={handleMouseLeaveStage}
  >
    <Layer id="background" imageSmoothingEnabled={imageSmoothing} listening={false}>
      {#each Object.entries(imagesPerView) as [view_name, images]}
        <Group id={`bg-${view_name}`} bind:this={backgroundViewRefs[view_name]}>
          {#each images as image, i}
            <KonvaImage
              image={image.element}
              name={image.id}
              id={i === images.length - 1 ? `image-${view_name}` : `image-prev-${view_name}-${i}`}
              listening={false}
            />
          {/each}
        </Group>
      {/each}
    </Layer>

    <Layer id="static">
      {#each Object.entries(imagesPerView) as [view_name, images]}
        {@const currentLoadedImage = images[images.length - 1]}
        {@const currentImage = currentLoadedImage?.element}
        {@const viewRef = { id: currentLoadedImage?.id ?? "", name: view_name }}
        <Group id={`static-${view_name}`} bind:this={staticViewRefs[view_name]}>
          {#if !isActivePaintingTool}
            {#each bboxesByView[view_name] ?? [] as bbox (bbox.id)}
              {#if !bbox.ui.displayControl.editing}
                <BBox2D
                  {bbox}
                  {colorScale}
                  zoomFactor={zoomFactor[view_name] ?? 1}
                  listening={false}
                  imageWidth={currentImage?.width ?? 0}
                  imageHeight={currentImage?.height ?? 0}
                  isInteracting={isViewportInteracting}
                  {merge}
                  {onNewShapeChange}
                />
              {/if}
            {/each}
          {/if}

          {#each masksByView[view_name] ?? [] as mask (mask.id)}
            {#if !mask.ui.displayControl.editing}
              <PolygonShape
                {viewRef}
                {newShape}
                {onNewShapeChange}
                {currentImage}
                zoomFactor={zoomFactor[view_name] ?? 1}
                {mask}
                color={isActivePaintingTool
                  ? "#9CA3AF"
                  : colorScale(
                      mask.ui.top_entities && mask.ui.top_entities.length > 0
                        ? mask.ui.top_entities[0].id
                        : mask.data.entity_id,
                    )}
                ghostOpacity={isActivePaintingTool ? 0.5 : undefined}
                {selectedTool}
                interactive={false}
                disableCache={isVideo}
              />
            {/if}
          {/each}

          {#if !isActivePaintingTool}
            <Group listening={false}>
              <ShowKeypoints
                {colorScale}
                {viewRef}
                keypoints={keypointsByView[view_name] ?? []}
                zoomFactor={zoomFactor[view_name] ?? 1}
                imageSize={{ width: currentImage?.width ?? 1, height: currentImage?.height ?? 1 }}
                {newShape}
                {onNewShapeChange}
                {isPlaybackActive}
              />
            </Group>
          {/if}
        </Group>
      {/each}
    </Layer>

    <Layer id="active">
      {#each Object.entries(imagesPerView) as [view_name, images]}
        {@const currentLoadedImage = images[images.length - 1]}
        {@const currentImage = currentLoadedImage?.element}
        {@const viewRef = { id: currentLoadedImage?.id ?? "", name: view_name }}
        <Group
          id={`active-${view_name}`}
          bind:this={activeViewRefs[view_name]}
          dragDistance={0}
          ondragstart={beginViewportInteraction}
          ondragmove={() => {
            syncLinkedViewGroupsFromActive(view_name);
            stage?.batchDraw();
          }}
          ondragend={() => {
            syncLinkedViewGroupsFromActive(view_name);
            endViewportInteraction();
          }}
        >
          <Rect
            x={0}
            y={0}
            width={currentImage?.width ?? 0}
            height={currentImage?.height ?? 0}
            fill="rgba(0,0,0,0.001)"
            strokeEnabled={false}
            onwheel={(event: Konva.KonvaEventObject<WheelEvent>) =>
              handleWheelOnImage(event.evt, view_name)}
            onpointerdown={(event: Konva.KonvaEventObject<PointerEvent>) =>
              handleClickOnImage(event.evt, viewRef)}
            onpointerup={() => handlePointerUpOnImage(viewRef)}
            ondblclick={() => handleDoubleClickOnImage(view_name)}
          />

          {#if draftRectangle && draftRectangle.viewRef.name === view_name}
            <CreateRectangle
              zoomFactor={zoomFactor[view_name] ?? 1}
              newShape={draftRectangle}
              {viewRef}
              editable={bboxEditable}
              isInteracting={isViewportInteracting}
              onTransformEnd={(geo: { x: number; y: number; width: number; height: number }) => {
                if (
                  localDraftShape?.status === "creating" &&
                  localDraftShape.type === ShapeType.bbox
                ) {
                  localDraftShape = {
                    ...localDraftShape,
                    x: geo.x,
                    y: geo.y,
                    width: geo.width,
                    height: geo.height,
                  };
                }
              }}
              onDragEnd={(pos: Point2D) => {
                if (
                  localDraftShape?.status === "creating" &&
                  localDraftShape.type === ShapeType.bbox
                ) {
                  localDraftShape = {
                    ...localDraftShape,
                    x: pos.x,
                    y: pos.y,
                  };
                }
              }}
            />
          {/if}

          {#if !isActivePaintingTool}
            {#each bboxesByView[view_name] ?? [] as bbox (bbox.id)}
              {#if !bbox.ui.displayControl.editing && selectedTool?.type === ToolType.Rectangle}
                <Rect
                  x={bbox.data.coords[0]}
                  y={bbox.data.coords[1]}
                  width={bbox.data.coords[2]}
                  height={bbox.data.coords[3]}
                  fill="rgba(0,0,0,0.001)"
                  strokeEnabled={false}
                  onpointerdown={(event: Konva.KonvaEventObject<PointerEvent>) => {
                    event.cancelBubble = true;
                    handleSelectBBox(bbox);
                  }}
                />
              {:else if !bbox.ui.displayControl.editing && selectedTool?.type === ToolType.Pan}
                <Rect
                  x={bbox.data.coords[0]}
                  y={bbox.data.coords[1]}
                  width={bbox.data.coords[2]}
                  height={bbox.data.coords[3]}
                  fill="rgba(0,0,0,0.001)"
                  strokeEnabled={false}
                  onclick={(event: Konva.KonvaEventObject<MouseEvent>) => {
                    event.cancelBubble = true;
                    handleSelectBBox(bbox);
                  }}
                />
              {/if}
            {/each}

            {#each bboxesByView[view_name] ?? [] as bbox (bbox.id)}
              {#if bbox.ui.displayControl.editing}
                <BBox2D
                  {bbox}
                  {colorScale}
                  zoomFactor={zoomFactor[view_name] ?? 1}
                  listening={true}
                  imageWidth={currentImage?.width ?? 0}
                  imageHeight={currentImage?.height ?? 0}
                  isInteracting={isViewportInteracting}
                  {merge}
                  {onNewShapeChange}
                />
              {/if}
            {/each}
          {/if}

          {#if draftPolygon && "viewRef" in draftPolygon && draftPolygon.viewRef?.name === view_name}
            <CreatePolygon
              {viewRef}
              newShape={draftPolygon}
              zoomFactor={zoomFactor[view_name] ?? 1}
              getRelativePointerOnView={() =>
                getViewLayer(view_name)?.getRelativePointerPosition() ?? null}
              onToolEvent={dispatchPolygonToolEvent}
              isInteracting={isViewportInteracting}
            />
          {/if}

          {#if selectedTool?.type === ToolType.Brush}
            <BrushMask
              bind:this={brushMaskRefs[view_name]}
              {viewRef}
              {currentImage}
              zoomFactor={zoomFactor[view_name] ?? 1}
              {selectedItemId}
              {selectedTool}
              {brushSettings}
            />
          {/if}

          {#each masksByView[view_name] ?? [] as mask (mask.id)}
            {#if mask.ui.displayControl.editing}
              <PolygonShape
                {viewRef}
                {newShape}
                {onNewShapeChange}
                {currentImage}
                zoomFactor={zoomFactor[view_name] ?? 1}
                {mask}
                color={colorScale(
                  mask.ui.top_entities && mask.ui.top_entities.length > 0
                    ? mask.ui.top_entities[0].id
                    : mask.data.entity_id,
                )}
                {selectedTool}
                interactive={true}
                disableCache={isVideo}
              />
            {/if}
          {/each}

          {#if !isActivePaintingTool}
            <ShowKeypoints
              {colorScale}
              {viewRef}
              keypoints={(keypointsByView[view_name] ?? []).filter(
                (kpt) => kpt.ui?.displayControl.editing,
              )}
              zoomFactor={zoomFactor[view_name] ?? 1}
              imageSize={{ width: currentImage?.width ?? 1, height: currentImage?.height ?? 1 }}
              {newShape}
              {onNewShapeChange}
              {isPlaybackActive}
            />
          {/if}
        </Group>
      {/each}
    </Layer>

    <Layer id="tools">
      <Crosshair position={crosshairPosition} {stageWidth} {stageHeight} />
      {#if brushCursorState}
        <BrushCursor
          x={brushCursorState.x}
          y={brushCursorState.y}
          radius={brushCursorState.radius}
          mode={brushCursorState.mode}
        />
      {/if}
    </Layer>
  </Stage>
</div>
<svelte:window onkeydown={handleKeyDown} />
