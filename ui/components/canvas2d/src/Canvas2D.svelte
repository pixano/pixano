<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import Konva from "konva";
  import { onDestroy, onMount, tick } from "svelte";
  import { Group, Image as KonvaImage, Layer, Stage } from "svelte-konva";
  import { writable, type Writable } from "svelte/store";

  import {
    ToolType,
    type BrushSelectionTool,
    type PreviewShape,
    type SelectionTool,
    type ToolEvent,
  } from "@pixano/tools";
  import {
    brushDrawTool,
    panTool,
    polygonTool,
    rectangleTool,
    toggleBrushMode,
  } from "./tooling/toolPolicy";
  import type { Filters } from "@pixano/dataset-item-workspace/src/lib/types/datasetItemWorkspaceTypes";
  import type {
    CanvasAnnotationLike,
    CanvasBBox,
    CanvasBBoxCreatingShape,
    CanvasBBoxSavingShape,
    CanvasImagesPerView,
    CanvasKeypoints,
    CanvasMask,
    CanvasPolygonCreatingShape,
    CanvasPolygonOutputMode,
    CanvasPolygonPoint,
    CanvasReference,
    CanvasShape,
  } from "./lib/types/canvasData";
  import { CanvasShapeType } from "./lib/types/canvasData";

  import { clearCurrentAnn } from "./api/boundingBoxesApi";
  import { clearParsedCache, convertPointToSvg, runLengthEncode } from "./api/maskApi";
  import { resizeStroke } from "./api/rectangleApi";
  import BrushCanvas from "./components/BrushCanvas.svelte";
  import CreateRectangle from "./components/CreateRectangle.svelte";
  import CreatePolygon from "./components/CreatePolygon.svelte";
  import PolygonGroup from "./components/PolygonGroup.svelte";
  import Rectangle from "./components/Rectangle.svelte";
  import ShowKeypoints from "./components/ShowKeypoint.svelte";
  import { equalizeHistogram } from "./lib/utils/equalizeHistogram";
  import { FilterManager } from "./lib/workers/filterManager";
  import type { FilterParams } from "./lib/workers/filterWorker";
  import type { ToolBridge } from "@pixano/store";

  import {
    createInternalToolBridge,
    createToolFSMForSelection,
  } from "./tooling/bridgeRuntime";
  import { getFallbackCanvasTool, handleToolShortcuts, isSupportedCanvasTool } from "./tooling/toolPolicy";

  interface BrushCanvasRef {
    beginStroke(x: number, y: number): void;
    updateStroke(x: number, y: number): void;
    endStroke(): void;
    getMaskData(): CanvasShape | null;
    clearCanvas(): void;
    destroy(): void;
  }

  // Exports
  export let selectedItemId: string;
  export let masks: CanvasMask[];
  export let bboxes: CanvasBBox[];
  export let keypoints: CanvasKeypoints[] = [];
  export let selectedTool: SelectionTool;
  export let newShape: CanvasShape;
  export let imagesPerView: CanvasImagesPerView;
  export let colorScale: (value: string) => string;
  export let isVideo: boolean = false;
  export let imageSmoothing: boolean = true;
  export let merge: (ann: CanvasAnnotationLike) => void = () => {
    return;
  };
  export let brushSettings: {
    brushRadius: number;
    lazyRadius: number;
    friction: number;
  } = {
    brushRadius: 20,
    lazyRadius: 10,
    friction: 0.15,
  };

  // New architecture (default behavior for the ongoing migration)
  export let useNewArchitecture: boolean = true;
  export let toolBridge: ToolBridge | undefined = undefined;

  // Image settings
  export let filters: Writable<Filters> = writable<Filters>();
  export let canvasSize: number = 0;

  let isReady = false;

  let numberOfBBoxes: number;
  let prevSelectedTool: SelectionTool;
  let zoomFactor: Record<string, number> = {}; // {view_name: zoomFactor}

  let lastInputViewRef: CanvasReference;

  // Brush tool state
  let brushCanvasRefs: Record<string, BrushCanvasRef> = {};
  let brushCursor: Konva.Circle | null = null;
  let brushLazyLine: Konva.Line | null = null;
  // Direct reference maps to avoid O(n) stage.findOne() lookups
  let viewLayerRefs: Record<string, Konva.Layer> = {};
  let imageRefs: Record<string, Konva.Image> = {};

  // Web Worker-based filter manager (off-thread filter computation)
  let filterManager: FilterManager | null = null;

  let bboxEditable = false;
  let internalToolBridge: ToolBridge | undefined;
  let activeToolBridge: ToolBridge | undefined;
  let cleanupToolBridgeSubscriptions: (() => void) | undefined;

  // True for active painting flows in the reduced Pan/Rectangle/Brush architecture.
  $: isActivePaintingTool = selectedTool?.type === ToolType.Brush;

  $: {
    const switchingBrushMode =
      prevSelectedTool?.type === ToolType.Brush && selectedTool?.type === ToolType.Brush;

    if (!switchingBrushMode || (newShape.status === "none" && newShape.shouldReset)) {
      clearAnnotationAndInputs();
    }
    prevSelectedTool = selectedTool;
  }

  $: {
    if (canvasSize && isReady) {
      for (const view_name of Object.keys(imagesPerView)) {
        scaleView(view_name);
      }
      canvasSize = 0;
    }
  }

  $: {
    if (newShape.status === "none" && newShape.shouldReset) {
      clearAnnotationAndInputs();
      // Consume the one-shot reset flag to avoid repeated cleanup on later tool toggles.
      newShape = { status: "none" };
    }
  }

  $: {
    if (stage && numberOfBBoxes !== bboxes?.length) {
      const rect: Konva.Rect = stage?.findOne("#drag-rect");
      if (rect) {
        rect.destroy();
      }
    }
    numberOfBBoxes = bboxes.length;
  }

  function clearRectangleTransformer() {
    const rect: Konva.Rect | undefined = stage?.findOne("#drag-rect");
    if (rect) {
      rect.off("transform.creation");
      rect.off("transformend.creation");
      rect.off("dragend.creation");
    }
    bboxEditable = false;
    const tr: Konva.Transformer | undefined = stage?.findOne("#transformer");
    if (tr) tr.nodes([]);
  }

  function enableRectangleEditing(viewRef: CanvasReference) {
    const rect: Konva.Rect | undefined = stage?.findOne("#drag-rect");
    if (!rect) return;

    clearRectangleTransformer();
    rect.on("transform.creation", () => {
      resizeStroke(rect);
    });
    rect.on("transformend.creation dragend.creation", () => {
      const viewLayer = getViewLayer(viewRef.name);
      if (!viewLayer) return;
      const correctedRect = rect.getClientRect({
        skipTransform: false,
        skipShadow: true,
        skipStroke: true,
        relativeTo: viewLayer,
      });
      newShape = {
        status: "creating",
        type: CanvasShapeType.BBox,
        x: correctedRect.x,
        y: correctedRect.y,
        width: correctedRect.width,
        height: correctedRect.height,
        viewRef,
      };
    });

    bboxEditable = true;
    const tr: Konva.Transformer | undefined = stage?.findOne("#transformer");
    if (tr) {
      tr.nodes([rect]);
      tr.getLayer()?.batchDraw();
    }
  }

  function toPolygonPoints(
    points: ReadonlyArray<{ x: number; y: number; id?: number }>,
  ): CanvasPolygonPoint[] {
    return points.map((point, index) => ({
      x: point.x,
      y: point.y,
      id: typeof point.id === "number" ? point.id : index,
    }));
  }

  function toClosedPolygonPoints(
    polygons: ReadonlyArray<ReadonlyArray<{ x: number; y: number; id?: number }>>,
  ): CanvasPolygonPoint[][] {
    return polygons.map((polygon) => toPolygonPoints(polygon));
  }

  function syncToolPreview(preview: PreviewShape | null) {
    const viewRef = lastInputViewRef;
    if (!viewRef) {
      if (
        newShape.status === "creating" &&
        (newShape.type === CanvasShapeType.BBox || newShape.type === CanvasShapeType.Polygon)
      ) {
        newShape = { status: "none" };
      }
      clearRectangleTransformer();
      return;
    }

    if (preview?.type === "polygon") {
      newShape = {
        status: "creating",
        type: CanvasShapeType.Polygon,
        viewRef,
        phase: preview.phase,
        closedPolygons: toClosedPolygonPoints(preview.closedPolygons),
        points: toPolygonPoints(preview.points),
        current: preview.current,
        hoveredEdge: preview.hoveredEdge ?? null,
        outputMode: selectedTool?.type === ToolType.Polygon ? selectedTool.outputMode : "polygon",
      } as CanvasPolygonCreatingShape;
      if (bboxEditable) {
        clearRectangleTransformer();
      }
      return;
    }

    if (preview?.type !== "rectangle") {
      if (
        newShape.status === "creating" &&
        (newShape.type === CanvasShapeType.BBox || newShape.type === CanvasShapeType.Polygon)
      ) {
        newShape = { status: "none" };
      }
      clearRectangleTransformer();
      return;
    }

    newShape = {
      status: "creating",
      type: CanvasShapeType.BBox,
      x: preview.origin.x,
      y: preview.origin.y,
      width: preview.current.x - preview.origin.x,
      height: preview.current.y - preview.origin.y,
      viewRef,
    };

    if (preview.editable) {
      void tick().then(() => {
        enableRectangleEditing(viewRef);
      });
    } else {
      if (bboxEditable) {
        clearRectangleTransformer();
      }
    }
  }

  function handleRectangleRequestSave(geometry: unknown) {
    const geo = geometry as { x: number; y: number; width: number; height: number };

    // Read final position from the Konva Transformer if it exists
    const rect: Konva.Rect | undefined = stage?.findOne("#drag-rect");
    const viewLayer = lastInputViewRef ? getViewLayer(lastInputViewRef.name) : undefined;
    const finalGeo =
      rect && viewLayer
        ? rect.getClientRect({
            skipTransform: false,
            skipShadow: true,
            skipStroke: true,
            relativeTo: viewLayer,
          })
        : geo;

    clearRectangleTransformer();

    const viewRef = lastInputViewRef;
    if (viewRef) {
      const currentImage = getCurrentImage(viewRef.name);
      newShape = {
        status: "saving",
        attrs: {
          x: finalGeo.x,
          y: finalGeo.y,
          width: finalGeo.width,
          height: finalGeo.height,
        },
        type: CanvasShapeType.BBox,
        viewRef,
        itemId: selectedItemId,
        imageWidth: currentImage.width,
        imageHeight: currentImage.height,
      };
    }
  }

  function handlePolygonRequestSave(geometry: unknown) {
    const payload = geometry as {
      polygons?: Array<Array<{ x: number; y: number; id?: number }>>;
      points?: Array<{ x: number; y: number }>;
      outputMode?: CanvasPolygonOutputMode;
    };
    const sourcePolygons: Array<Array<{ x: number; y: number; id?: number }>> =
      Array.isArray(payload.polygons) && payload.polygons.length > 0
        ? payload.polygons
        : Array.isArray(payload.points) && payload.points.length > 0
          ? [payload.points.map((point) => ({ x: point.x, y: point.y }))]
          : [];
    if (sourcePolygons.length === 0) return;

    const viewRef = lastInputViewRef;
    if (!viewRef) return;

    const currentImage = getCurrentImage(viewRef.name);
    const polygonMode: CanvasPolygonOutputMode = payload.outputMode ?? "polygon";
    const polygonPoints = sourcePolygons
      .map((polygon) =>
        polygon.map((point, id) => ({
          x: polygonMode === "mask" ? Math.round(point.x) : point.x,
          y: polygonMode === "mask" ? Math.round(point.y) : point.y,
          id: typeof point.id === "number" ? point.id : id,
        })),
      )
      .filter((polygon) => polygon.length >= 3);
    if (polygonPoints.length === 0) return;

    const polygonSvg = polygonPoints.map((polygon) => convertPointToSvg(polygon));
    cleanupPolygonPreviewListeners();

    if (polygonMode === "mask") {
      const counts = runLengthEncode(polygonSvg, currentImage.width, currentImage.height);
      newShape = {
        status: "saving",
        type: CanvasShapeType.Mask,
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
      };
      return;
    }

    newShape = {
      status: "saving",
      type: CanvasShapeType.Polygon,
      masksImageSVG: polygonSvg,
      viewRef,
      itemId: selectedItemId,
      imageWidth: currentImage.width,
      imageHeight: currentImage.height,
      polygonMode,
      polygonPoints,
    };
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

  $: if (useNewArchitecture && selectedTool && !isSupportedCanvasTool(selectedTool)) {
    selectedTool = getFallbackCanvasTool();
  }

  $: {
    const bridge = useNewArchitecture ? toolBridge ?? internalToolBridge : undefined;
    if (bridge !== activeToolBridge) {
      cleanupToolBridgeSubscriptions?.();
      activeToolBridge = bridge;

      if (bridge) {
        bridge.onRequestSave(handleToolRequestSave);
        const unsubscribePreview = bridge.preview.subscribe((preview) => {
          syncToolPreview(preview);
        });
        cleanupToolBridgeSubscriptions = () => {
          unsubscribePreview();
        };
      } else {
        cleanupToolBridgeSubscriptions = undefined;
      }
    }
  }

  $: if (useNewArchitecture && activeToolBridge && selectedTool) {
    const fsm = createToolFSMForSelection(selectedTool);
    if (fsm) {
      activeToolBridge.switchTool(fsm);
    }
  }

  // References to HTML Elements
  let stageContainer: HTMLElement;

  // References to Konva Elements
  let stage: Konva.Stage;
  let toolsLayer: Konva.Layer;
  let transformer = new Konva.Transformer({
    id: "transformer",
    rotateEnabled: false,
  });

  // Main konva stage configuration
  let stageConfig: Konva.ContainerConfig = {
    width: 512,
    height: 780,
    name: "konva",
    id: "stage",
  };

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
      if (stage.width() !== width || stage.height() !== height) {
        stage.width(width);
        stage.height(height);
        if (isReady) {
          for (const view_name of Object.keys(imagesPerView)) {
            scaleView(view_name);
          }
        }
        stage.batchDraw();
      }
    }
  });

  // ********** INIT ********** //

  onMount(() => {
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

    loadItem();
    // Fire stage events observers
    resizeObserver.observe(stageContainer);
  });

  onDestroy(() => {
    clearAnnotationAndInputs();
    filterManager?.destroy();
    filterManager = null;
    cleanupToolBridgeSubscriptions?.();
    cleanupToolBridgeSubscriptions = undefined;
  });

  // --- Targeted reactive statements (replaces monolithic afterUpdate) ---

  // React to item changes
  $: if (selectedItemId && currentId !== selectedItemId) {
    loadItem();
  }

  // React to tool changes
  $: if (stage && selectedTool) {
    handleChangeTool();
  } else if (stage && !selectedTool) {
    stage.container().style.cursor = "default";
  }

  // Attach transformer when views change
  $: if (stage && imagesPerView) {
    // Use tick to ensure DOM is updated before accessing layers
    void tick().then(() => {
      Object.keys(imagesPerView).forEach((view_name) => {
        const viewLayer: Konva.Layer = stage?.findOne(`#${view_name}`);
        if (viewLayer) viewLayer.add(transformer);
      });
    });
  }

  // React to filter changes (debounced, skip for video)
  let filterDebounceTimer: ReturnType<typeof setTimeout>;
  $: if (!isVideo && stage && $filters) {
    clearTimeout(filterDebounceTimer);
    filterDebounceTimer = setTimeout(() => applyFilters(), 50);
  }

  let scaleOnFirstLoad = {};
  let viewReady = {};
  Object.keys(imagesPerView).forEach((view_name) => {
    //we need a first scaleView for image only. If video, the scale is done elsewhere
    scaleOnFirstLoad[view_name] = !isVideo;
    viewReady[view_name] = false;
  });

  /** Get a view layer by name using cached ref (O(1)) with fallback. */
  function getViewLayer(view_name: string): Konva.Layer | undefined {
    return viewLayerRefs[view_name] ?? stage?.findOne(`#${view_name}`);
  }

  /** Get the image node for a view using cached ref (O(1)) with fallback. */
  function getImageNode(view_name: string): Konva.Image | undefined {
    return imageRefs[view_name] ?? stage?.findOne(`#image-${view_name}`);
  }

  /** Register an image ref when image loads. */
  function registerImageRef(view_name: string) {
    // Called after image onload; find the image node in the now-populated layer
    const img: Konva.Image | undefined = stage?.findOne(`#image-${view_name}`);
    if (img) imageRefs[view_name] = img;
  }

  const getCurrentImage = (view_name: string) =>
    imagesPerView[view_name][imagesPerView[view_name].length - 1].element;

  function loadItem() {
    const keys = Object.keys(imagesPerView);
    const totalKeys = keys.length;

    // Calculate new grid size
    gridSize.cols = Math.ceil(Math.sqrt(totalKeys));
    gridSize.rows = Math.ceil(totalKeys / gridSize.cols);

    // Clear annotations in case a previous item was already loaded
    if (currentId) clearAnnotationAndInputs();
    clearParsedCache();

    // Reset flags for the new item
    isReady = false;
    scaleOnFirstLoad = {};
    viewReady = {};
    keys.forEach((view_name) => {
      scaleOnFirstLoad[view_name] = !isVideo;
      viewReady[view_name] = false;
    });

    keys.forEach((view_name) => {
      const currentImage = getCurrentImage(view_name);

      const onImageReady = () => {
        registerImageRef(view_name);
        if (scaleOnFirstLoad[view_name]) {
          if (scaleView(view_name)) {
            scaleOnFirstLoad[view_name] = false;
          }
        }
        //scaleElements(view_name);
        viewReady[view_name] = true;
        if (Object.values(viewReady).every(Boolean)) {
          isReady = true;
        }
        if (!isVideo) cacheImage();
      };

      currentImage.onload = onImageReady;
      // Handle already-loaded images (e.g., from browser cache)
      if (currentImage.complete && currentImage.naturalWidth > 0) {
        onImageReady();
      }
    });

    currentId = selectedItemId;
  }

  function scaleView(view_name: string): boolean {
    const viewLayer = getViewLayer(view_name);
    if (!viewLayer) {
      return false;
    }
    // Calculate max dims for every image in the grid
    const maxWidth = stageContainer.getBoundingClientRect().width / gridSize.cols;
    const maxHeight = stageContainer.getBoundingClientRect().height / gridSize.rows;

    // Get view index
    const keys = Object.keys(imagesPerView);
    const i = keys.findIndex((view) => view === view_name);

    // Calculate view position in grid
    const grid_pos = {
      x: i % gridSize.cols,
      y: Math.floor(i / gridSize.cols),
    };

    // Fit stage
    const currentImage = getCurrentImage(view_name);
    const scaleByHeight = maxHeight / currentImage.height;
    const scaleByWidth = maxWidth / currentImage.width;
    const scale = Math.min(scaleByWidth, scaleByHeight);

    // Set zoomFactor for view
    zoomFactor[view_name] = scale;
    viewLayer.scale({ x: scale, y: scale });

    // Center view
    const offsetX = (maxWidth - currentImage.width * scale) / 2 + grid_pos.x * maxWidth;
    const offsetY = (maxHeight - currentImage.height * scale) / 2 + grid_pos.y * maxHeight;
    viewLayer.x(offsetX);
    viewLayer.y(offsetY);
    return true;
  }

  const cacheImage = () => {
    if (!stage) return;

    for (const view_name of Object.keys(imagesPerView)) {
      const image = getImageNode(view_name);
      if (!image || image.width() === 0 || image.height() === 0) continue;
      image.cache();
    }
  };

  const AdjustChannels = (imageData: ImageData) => {
    const { data } = imageData;

    const redMin = $filters.redRange[0];
    const redMax = $filters.redRange[1];
    const greenMin = $filters.greenRange[0];
    const greenMax = $filters.greenRange[1];
    const blueMin = $filters.blueRange[0];
    const blueMax = $filters.blueRange[1];

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
  };

  const applyFilters = () => {
    if (!stage) return;

    const workerFilters: FilterParams = {
      brightness: $filters.brightness,
      contrast: $filters.contrast,
      redRange: $filters.redRange as [number, number],
      greenRange: $filters.greenRange as [number, number],
      blueRange: $filters.blueRange as [number, number],
      equalizeHistogram: $filters.equalizeHistogram,
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
          // Draw source onto a temp canvas to get ImageData
          const tempCanvas = document.createElement("canvas");
          tempCanvas.width = sourceElement.width;
          tempCanvas.height = sourceElement.height;
          const tempCtx = tempCanvas.getContext("2d");
          if (tempCtx) {
            tempCtx.drawImage(sourceElement, 0, 0);
            filterManager.applyFilters(view_name, tempCanvas, workerFilters);
            continue;
          }
        }
      }

      // Fallback: synchronous Konva filter pipeline
      let filtersList = [Konva.Filters.Brighten, Konva.Filters.Contrast, AdjustChannels];
      if ($filters.equalizeHistogram) filtersList.push(equalizeHistogram);

      image.filters(filtersList);
      image.brightness($filters.brightness);
      image.contrast($filters.contrast);
    }
  };

  // ********** TOOLS ********** //

  function handleChangeTool() {
    // make sure tools layer is always on top
    if (toolsLayer) toolsLayer.moveToTop();

    if (selectedTool?.type === ToolType.Pan) {
      const crossline = stage.findOne("#crossline");
      if (crossline) crossline.destroy();
      cleanupPolygonPreviewListeners();
      stage.container().style.cursor = panTool.cursor;
      return;
    }

    if (selectedTool?.type === ToolType.Rectangle) {
      cleanupPolygonPreviewListeners();
      displayCrosshair(rectangleTool.cursor);
      return;
    }

    if (selectedTool?.type === ToolType.Polygon) {
      displayCrosshair(polygonTool.cursor);
      return;
    }

    if (selectedTool?.type === ToolType.Brush) {
      cleanupPolygonPreviewListeners();
      stage.container().style.cursor = "none";
      return;
    }

    cleanupPolygonPreviewListeners();
    stage.container().style.cursor = "default";
  }

  function updateBrushCursor(mousePos: Konva.Vector2d) {
    if (!toolsLayer) return;

    const mode = (selectedTool as BrushSelectionTool).mode;
    const cursorColor = mode === "draw" ? "rgba(0, 200, 0, 0.7)" : "rgba(200, 0, 0, 0.7)";

    if (!brushCursor) {
      brushCursor = new Konva.Circle({
        id: "brush-cursor",
        x: 0,
        y: 0,
        radius: brushSettings.brushRadius,
        stroke: cursorColor,
        strokeWidth: 2,
        fill: mode === "draw" ? "rgba(0, 200, 0, 0.1)" : "rgba(200, 0, 0, 0.1)",
        listening: false,
      });
      toolsLayer.add(brushCursor);
    }

    brushCursor.radius(brushSettings.brushRadius);
    brushCursor.stroke(cursorColor);
    brushCursor.fill(mode === "draw" ? "rgba(0, 200, 0, 0.1)" : "rgba(200, 0, 0, 0.1)");
    brushCursor.x(mousePos.x);
    brushCursor.y(mousePos.y);
    brushCursor.show();
  }

  $: if (brushCursor && selectedTool?.type === ToolType.Brush) {
    brushCursor.radius(brushSettings.brushRadius);
    brushCursor.getLayer()?.batchDraw();
  }

  function cleanupBrushCursor() {
    if (brushCursor) {
      brushCursor.destroy();
      brushCursor = null;
    }
    if (brushLazyLine) {
      brushLazyLine.destroy();
      brushLazyLine = null;
    }
  }

  function handleBrushPointerDown(viewRef: CanvasReference) {
    const viewLayer = getViewLayer(viewRef.name);
    const pos = viewLayer.getRelativePointerPosition();
    if (!pos) return;

    const brushCanvas = brushCanvasRefs[viewRef.name];
    if (brushCanvas) {
      brushCanvas.beginStroke(pos.x, pos.y);
    }
  }

  function handleBrushPointerMove(view_name: string) {
    const viewLayer = getViewLayer(view_name);
    const pos = viewLayer.getRelativePointerPosition();
    if (!pos) return;

    const brushCanvas = brushCanvasRefs[view_name];
    if (brushCanvas) {
      brushCanvas.updateStroke(pos.x, pos.y);
    }
  }

  function handleBrushPointerUp(view_name: string) {
    const brushCanvas = brushCanvasRefs[view_name];
    if (brushCanvas) {
      brushCanvas.endStroke();
    }
    // Clean up layer-level drag listeners (same pattern as Rectangle/Keypoint)
    const viewLayer = getViewLayer(view_name);
    if (viewLayer) {
      viewLayer.off("pointermove.brush");
      viewLayer.off("pointerup.brush");
    }
  }

  function saveBrushMask(view_name: string) {
    const brushCanvas = brushCanvasRefs[view_name];
    if (brushCanvas) {
      const maskData = brushCanvas.getMaskData();
      if (maskData) {
        newShape = maskData;
      }
    }
  }

  function cleanupAllBrushCanvases() {
    for (const key of Object.keys(brushCanvasRefs)) {
      const brushCanvas = brushCanvasRefs[key];
      if (brushCanvas) {
        brushCanvas.destroy();
      }
    }
    brushCanvasRefs = {};
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

  function displayCrosshair(cursor: string) {
    if (!toolsLayer) return;
    stage.container().style.cursor = cursor;
  }

  function updateCrosshairState(mousePos: Konva.Vector2d) {
    const scale = stage.scaleX();
    const lineScale = Math.max(1, 1 / scale);

    const [xLimit, yLimit] = findOrCreateCrosshair();
    const stageHeight = stage.height();
    xLimit.scaleY(lineScale);
    xLimit.points([mousePos.x, 0, mousePos.x, stageHeight]);
    const stageWidth = stage.width();
    yLimit.scaleX(lineScale);
    yLimit.points([0, mousePos.y, stageWidth, mousePos.y]);
  }

  function findOrCreateCrosshair(): Konva.Line[] {
    const stageHeight = stage.height();
    const stageWidth = stage.width();
    let crossLineGroup: Konva.Group = toolsLayer.findOne("#crossline");
    let xLimit: Konva.Line;
    let yLimit: Konva.Line;
    if (crossLineGroup) {
      xLimit = crossLineGroup.findOne("#xline");
      yLimit = crossLineGroup.findOne("#yline");
    } else {
      crossLineGroup = new Konva.Group({ id: "crossline" });
      xLimit = new Konva.Line({
        id: "xline",
        points: [0, 0, 0, stageHeight],
        stroke: "white",
        strokeWidth: 1,
        opacity: 0.75,
        dash: [5, 1],
      });
      yLimit = new Konva.Line({
        id: "yline",
        points: [0, 0, stageWidth, 0],
        stroke: "white",
        strokeWidth: 1,
        opacity: 0.75,
        dash: [5, 1],
      });
      crossLineGroup.add(xLimit);
      crossLineGroup.add(yLimit);
      toolsLayer.add(crossLineGroup);
    }
    return [xLimit, yLimit];
  }

  function clearAnnotationAndInputs() {
    if (!stage) return;
    for (const view_name of Object.keys(imagesPerView)) {
      clearCurrentAnn(view_name, stage, selectedTool);
    }
    if (selectedTool) {
      stage.container().style.cursor = selectedTool.cursor;
    }
    const crossline = toolsLayer?.findOne("#crossline");
    if (crossline) crossline.destroy();
    cleanupBrushCursor();
    cleanupPolygonPreviewListeners();
    // Only clear brush canvases after the user confirms (shouldReset) or
    // when leaving the brush tool — NOT while the save form is open.
    if (newShape.status !== "saving") {
      if (selectedTool?.type !== ToolType.Brush || newShape.shouldReset) {
        for (const key of Object.keys(brushCanvasRefs)) {
          brushCanvasRefs[key]?.clearCanvas();
        }
      }
    }
  }

  // ********** MOUSE EVENTS ********** //

  function handleMouseMoveStage() {
    const position = stage.getRelativePointerPosition();
    if (!position) return;

    if (
      selectedTool?.type === ToolType.Rectangle ||
      selectedTool?.type === ToolType.Polygon ||
      selectedTool?.type === ToolType.Brush
    ) {
      updateCrosshairState(position);
    }

    if (selectedTool?.type === ToolType.Brush) {
      updateBrushCursor(position);
      for (const view_name of Object.keys(imagesPerView)) {
        handleBrushPointerMove(view_name);
      }
    }
  }

  function handleMouseEnterStage() {
    for (const tool of toolsLayer.children) {
      tool.show();
    }
  }

  function handleMouseLeaveStage() {
    for (const tool of toolsLayer.children) {
      tool.hide();
    }
    // End any ongoing brush stroke when mouse leaves
    if (selectedTool?.type === ToolType.Brush) {
      for (const view_name of Object.keys(imagesPerView)) {
        handleBrushPointerUp(view_name);
      }
    }
  }

  function handleDragEndOnView(view_name: string) {
    const viewLayer = getViewLayer(view_name);
    viewLayer.draggable(false);
    viewLayer.off("dragend dragmove");
  }

  function handlePointerUpOnImage(viewRef: CanvasReference) {
    const viewLayer = getViewLayer(viewRef.name);
    viewLayer.draggable(false);
    viewLayer.off("dragend dragmove");

    if (selectedTool?.type === ToolType.Brush) {
      handleBrushPointerUp(viewRef.name);
    }
  }

  function handleDoubleClickOnImage(view_name: string) {
    // put double-clickd view on top of views
    const viewLayer = getViewLayer(view_name);
    viewLayer.moveToTop();
    //keeps tools on top
    toolsLayer.moveToTop();
  }

  function handleClickOnImage(event: PointerEvent, viewRef: CanvasReference) {
    const viewLayer = getViewLayer(viewRef.name);

    if (
      (newShape.status === "none" || newShape.status === "editing") &&
      selectedTool?.type !== ToolType.Brush &&
      selectedTool?.type !== ToolType.Polygon
    ) {
      newShape = {
        status: "editing",
        viewRef,
        type: "none",
        shapeId: null,
        highlighted: "all",
      };
    }
    if (selectedTool?.type === ToolType.Pan || event.button === 1) {
      viewLayer.draggable(true);
      viewLayer.on("dragmove", handleMouseMoveStage);
      viewLayer.on("dragend", () => handleDragEndOnView(viewRef.name));
    } else if (selectedTool?.type === ToolType.Brush) {
      handleBrushPointerDown(viewRef);
      viewLayer.on("pointermove.brush", () => handleBrushPointerMove(viewRef.name));
      viewLayer.on("pointerup.brush", () => handleBrushPointerUp(viewRef.name));
    } else if (selectedTool?.type === ToolType.Rectangle && !bboxEditable) {
      const bridge = activeToolBridge;
      if (!bridge) return;

      lastInputViewRef = viewRef;
      bridge.setCanvasContext(viewRef.name, stage.width(), stage.height());
      const pos = viewLayer.getRelativePointerPosition();
      if (!pos) return;
      bridge.dispatchEvent({
        type: "pointerDown",
        position: { x: pos.x, y: pos.y },
        button: event.button,
      });
      viewLayer.on("pointermove", () => {
        const movePos = viewLayer.getRelativePointerPosition();
        bridge.dispatchEvent({
          type: "pointerMove",
          position: { x: movePos.x, y: movePos.y },
        });
      });
      viewLayer.on("pointerup", () => {
        const upPos = viewLayer.getRelativePointerPosition();
        bridge.dispatchEvent({
          type: "pointerUp",
          position: { x: upPos.x, y: upPos.y },
        });
        viewLayer.off("pointermove");
        viewLayer.off("pointerup");
      });
    } else if (selectedTool?.type === ToolType.Polygon) {
      if (event.button !== 0) return;
      const bridge = activeToolBridge;
      if (!bridge) return;

      lastInputViewRef = viewRef;
      bridge.setCanvasContext(viewRef.name, stage.width(), stage.height());
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

  function zoom(stage: Konva.Stage, direction: number, view_name: string): number {
    // Defines zoom speed
    const zoomScale = 1.05;

    const viewLayer = getViewLayer(view_name);

    // Get old scaling
    const oldScale = viewLayer.scaleX();

    // Get mouse position
    const pointer = stage.getRelativePointerPosition();
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
    viewLayer.scale({ x: newScale, y: newScale });
    viewLayer.position(newPos);

    return newScale;
  }

  function handleWheelOnImage(event: WheelEvent, view_name: string) {
    // Prevent default scrolling
    event.preventDefault();

    // Get zoom direction
    let direction = event.deltaY < 0 ? 1 : -1;

    // Revert direction for trackpad
    if (event.ctrlKey) direction = -direction;

    // Zoom
    zoomFactor[view_name] = zoom(stage, direction, view_name);
  }

  const asRectangleShape = (
    shape: CanvasShape,
  ): CanvasBBoxCreatingShape | CanvasBBoxSavingShape =>
    shape as CanvasBBoxCreatingShape | CanvasBBoxSavingShape;

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
      const shouldKeepPolygonTool =
        selectedTool?.type === ToolType.Polygon &&
        newShape.status === "creating" &&
        newShape.type === CanvasShapeType.Polygon &&
        (newShape as CanvasPolygonCreatingShape).phase === "drawing" &&
        (newShape as CanvasPolygonCreatingShape).closedPolygons.length > 0;

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
      newShape = { status: "none", shouldReset: true };
      selectedTool = panTool;
      return;
    }

    const shortcutHandled = handleToolShortcuts(event, selectedTool, {
      selectPan: () => (selectedTool = panTool),
      selectRectangle: () => (selectedTool = rectangleTool),
      selectPolygon: () => (selectedTool = polygonTool),
      selectBrushDraw: () => (selectedTool = brushDrawTool),
      toggleBrushMode: () => {
        if (selectedTool?.type === ToolType.Brush) {
          selectedTool = toggleBrushMode(selectedTool);
        }
      },
      adjustBrushRadius: (delta) => {
        brushSettings = {
          ...brushSettings,
          brushRadius: Math.max(1, Math.min(100, brushSettings.brushRadius + delta)),
        };
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
</script>

<div
  class={`h-full bg-canvas transition-opacity duration-300 delay-100 relative ${isReady ? "" : "opacity-0"}`}
  bind:this={stageContainer}
>
  <Stage
    bind:config={stageConfig}
    bind:handle={stage}
    on:mousemove={handleMouseMoveStage}
    on:mouseenter={handleMouseEnterStage}
    on:mouseleave={handleMouseLeaveStage}
  >
    {#each Object.entries(imagesPerView) as [view_name, images]}
      <Layer
        config={{ id: view_name, imageSmoothingEnabled: imageSmoothing }}
        on:wheel={(event) => handleWheelOnImage(event.detail.evt, view_name)}
        bind:handle={viewLayerRefs[view_name]}
      >
        {#each images as image, i}
          <!-- images contain the current image and previous one, to prevent flashing (should exist better way...) -->
          {@const viewRef = { id: image.id, name: view_name }}
          <KonvaImage
            config={{
              image: image.element,
              name: image.id, //we use this to keep view id when there is no better way to get it
              id: `image-${view_name}`,
            }}
            on:pointerdown={(event) => handleClickOnImage(event.detail.evt, viewRef)}
            on:pointerup={() => handlePointerUpOnImage(viewRef)}
            on:dblclick={() => handleDoubleClickOnImage(view_name)}
          />
          <!-- Note: prevent drawing shapes on the "cached" image -->
          {#if i === images.length - 1}
            <Group
              config={{
                id: `bboxes-${view_name}`,
                listening:
                  selectedTool?.type === ToolType.Pan || selectedTool?.type === ToolType.Rectangle,
              }}
            >
              {#if (newShape.status === "creating" && newShape.type === CanvasShapeType.BBox) || (newShape.status === "saving" && newShape.type === CanvasShapeType.BBox)}
                <CreateRectangle
                  zoomFactor={zoomFactor[view_name]}
                  newShape={asRectangleShape(newShape)}
                  {stage}
                  {viewRef}
                  editable={bboxEditable}
                />
              {/if}
              {#each bboxes as bbox}
                {#if bbox.data.view_ref.name === view_name && !isActivePaintingTool}
                  <Rectangle
                    {bbox}
                    {colorScale}
                    zoomFactor={zoomFactor[view_name]}
                    {stage}
                    bind:newShape
                    {selectedTool}
                    {merge}
                  />
                {/if}
              {/each}
            </Group>
            <Group
              config={{
                id: `masks-${view_name}`,
                listening:
                  selectedTool?.type === ToolType.Pan || selectedTool?.type === ToolType.Polygon,
              }}
            >
              {#if (newShape.status === "creating" && newShape.type === CanvasShapeType.Polygon) || (newShape.status === "saving" && (newShape.type === CanvasShapeType.Polygon || (newShape.type === CanvasShapeType.Mask && "polygonMode" in newShape)))}
                <CreatePolygon
                  {viewRef}
                  {newShape}
                  {stage}
                  {zoomFactor}
                  onToolEvent={dispatchPolygonToolEvent}
                />
              {/if}
              {#if selectedTool?.type === ToolType.Brush}
                <BrushCanvas
                  bind:this={brushCanvasRefs[view_name]}
                  {viewRef}
                  {stage}
                  viewLayer={viewLayerRefs[view_name]}
                  currentImage={getCurrentImage(view_name)}
                  {zoomFactor}
                  {selectedItemId}
                  {selectedTool}
                  {brushSettings}
                />
              {/if}
              {#each masks as mask (mask.id)}
                {#if mask.data.view_ref.name === view_name}
                  <PolygonGroup
                    {viewRef}
                    bind:newShape
                    {stage}
                    currentImage={getCurrentImage(view_name)}
                    {zoomFactor}
                    {mask}
                    color={isActivePaintingTool
                      ? "#9CA3AF"
                      : colorScale(
                          mask.ui.top_entities && mask.ui.top_entities.length > 0
                            ? mask.ui.top_entities[0].id
                            : mask.data.entity_ref.id,
                        )}
                    ghostOpacity={isActivePaintingTool ? 0.5 : undefined}
                    {selectedTool}
                  />
                {/if}
              {/each}
            </Group>
            <Group
              config={{
                id: `keypoints-${view_name}`,
                listening: false,
              }}
            >
              {#if !isActivePaintingTool}
                <ShowKeypoints
                  {colorScale}
                  {stage}
                  {viewRef}
                  {keypoints}
                  zoomFactor={zoomFactor[view_name]}
                  {newShape}
                />
              {/if}
            </Group>
            <Group config={{ id: "currentAnnotation" }} />
          {/if}
        {/each}
      </Layer>
    {/each}

    <Layer config={{ name: "tools" }} bind:handle={toolsLayer} />
  </Stage>
</div>
<svelte:window on:keydown={handleKeyDown} />
