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
  import {
    computeCursorFlushAction,
    computeToolChangeAction,
    getToolSwitchSignature,
  } from "./canvasEventHandlers";
  import { zoomViewTransform } from "./canvasGeometry";
  import CreateMultiPath from "./CreateMultiPath.svelte";
  import CreateRectangle from "./CreateRectangle.svelte";
  import Crosshair from "./Crosshair.svelte";
  import { CanvasFilterPipeline } from "./filterPipeline";
  import { INTERACTION_COOLDOWN_MS } from "./konvaConstants";
  import Mask from "./Mask.svelte";
  import MultiPathShape from "./MultiPathShape.svelte";
  import {
    buildPolygonSaveShape,
    buildPolylineSaveShape,
    buildRectangleSaveShape,
    toClosedPolygonPoints,
    toPolygonPoints,
    type PolygonSavePayload,
  } from "./shapeSaveOps";
  import ShowKeypoints from "./ShowKeypoint.svelte";
  import { ViewRefManager } from "./viewRefs";
  import { highlightedEntity } from "$lib/stores/workspaceStores.svelte";
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
    polylineTool,
    rectangleTool,
    toggleBrushMode,
  } from "$lib/tools/canvasToolPolicy";
  import type {
    BBox,
    Mask as DatasetMask,
    MultiPath as DatasetMultiPath,
    LoadedImagesPerView,
    Reference,
  } from "$lib/types/dataset";
  import {
    ShapeType,
    type CreatePolygonShape,
    type CreatePolylineShape,
    type CreateRectangleShape,
    type ImageFilters,
    type KeypointAnnotation,
    type SaveRectangleShape,
    type Shape,
  } from "$lib/types/shapeTypes";
  import type { ToolBridge } from "$lib/types/store";

  interface BrushSettings {
    brushRadius: number;
    lazyRadius: number;
    friction: number;
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

  interface Props {
    // Exports
    selectedItemId: string;
    masks: DatasetMask[];
    bboxes: BBox[];
    multiPaths?: DatasetMultiPath[];
    keypoints?: KeypointAnnotation[];
    selectedTool: SelectionTool;
    newShape: Shape;
    imagesPerView: LoadedImagesPerView;
    colorScale: (value: string) => string;
    enableRenderCache?: boolean;
    imageSmoothing?: boolean;
    isPlaybackActive?: boolean;
    merge?: (ann: unknown) => void;
    brushSettings?: BrushSettings;
    onSelectedToolChange?: (tool: SelectionTool) => void;
    onNewShapeChange?: (shape: Shape) => void;
    onBrushSettingsChange?: (settings: BrushSettings) => void;
    toolBridge?: ToolBridge | undefined;
    // Image settings
    filters?: ImageFilters;
    canvasSize?: number;
    confirmKeys?: string[];
  }

  let {
    selectedItemId,
    masks,
    bboxes,
    multiPaths = [],
    keypoints = [],
    selectedTool,
    newShape,
    imagesPerView,
    colorScale,
    enableRenderCache = true,
    imageSmoothing = true,
    isPlaybackActive = false,
    merge,
    brushSettings = DEFAULT_BRUSH_SETTINGS,
    onSelectedToolChange,
    onNewShapeChange,
    onBrushSettingsChange,
    toolBridge = undefined,
    filters = DEFAULT_FILTERS,
    canvasSize = 0,
    confirmKeys = [],
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

  // Centralized view-group and image ref management
  const viewRefs = new ViewRefManager(() => stage);

  // Filter pipeline (Web Worker + fallback)
  const filterPipeline = new CanvasFilterPipeline(
    (name) => viewRefs.getImageNode(name),
    getCurrentImage,
  );

  let bboxEditable = $state(false);
  let rectangleSavePending = false;
  let internalToolBridge: ToolBridge | undefined = $state();
  let activeToolBridge: ToolBridge | undefined = $state();
  let lastBridgeForToolSwitch: ToolBridge | undefined = undefined;
  let lastToolSwitchSignature: string | null = null;

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
    }, INTERACTION_COOLDOWN_MS);
  }

  let draftOrSavingShape = $derived.by<Shape | null>(() => {
    if (localDraftShape) return localDraftShape;
    if (
      newShape.status === "saving" &&
      (newShape.type === ShapeType.bbox ||
        newShape.type === ShapeType.polygon ||
        newShape.type === ShapeType.polyline ||
        newShape.type === ShapeType.mask)
    ) {
      return newShape;
    }
    return null;
  });

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

    if (preview?.type === "polyline") {
      localDraftShape = {
        status: "creating",
        type: ShapeType.polyline,
        viewRef,
        phase: preview.phase,
        closedPolygons: toClosedPolygonPoints(preview.closedPolygons),
        points: toPolygonPoints(preview.points),
        current: preview.current,
        hoveredEdge: preview.hoveredEdge ?? null,
      } as CreatePolylineShape;
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
    const viewRef = lastInputViewRef;
    const currentImage = viewRef ? getCurrentImage(viewRef.name) : undefined;

    const saveShape = viewRef
      ? buildRectangleSaveShape(geo, localDraftShape, viewRef, selectedItemId, currentImage)
      : null;

    localDraftShape = null;
    clearRectangleTransformer();

    if (saveShape) {
      rectangleSavePending = true;
      onNewShapeChange?.(saveShape);
    }
  }

  function handlePolygonRequestSave(geometry: unknown): void {
    const payload = geometry as PolygonSavePayload;
    const viewRef = lastInputViewRef;
    if (!viewRef) return;

    const currentImage = getCurrentImage(viewRef.name);
    const outputMode =
      selectedTool?.type === ToolType.Polygon ? selectedTool.outputMode : "polygon";
    const saveShape = buildPolygonSaveShape(
      payload,
      viewRef,
      selectedItemId,
      currentImage,
      outputMode,
    );

    if (!saveShape) return;

    localDraftShape = null;
    cleanupPolygonPreviewListeners();
    onNewShapeChange?.(saveShape);
  }

  function handlePolylineRequestSave(geometry: unknown): void {
    const payload = geometry as PolygonSavePayload;
    const viewRef = lastInputViewRef;
    if (!viewRef) return;

    const currentImage = getCurrentImage(viewRef.name);
    const saveShape = buildPolylineSaveShape(payload, viewRef, selectedItemId, currentImage);

    if (!saveShape) return;

    localDraftShape = null;
    cleanupPolygonPreviewListeners();
    onNewShapeChange?.(saveShape);
  }

  function handleToolRequestSave(
    shapeType: "bbox" | "polygon" | "polyline" | "mask" | "keypoints",
    geometry: unknown,
  ) {
    if (shapeType === "bbox") {
      handleRectangleRequestSave(geometry);
      return;
    }

    if (shapeType === "polygon") {
      handlePolygonRequestSave(geometry);
      return;
    }

    if (shapeType === "polyline") {
      handlePolylineRequestSave(geometry);
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
    if (!toolBridge) {
      internalToolBridge = createInternalToolBridge(selectedItemId);
    }

    Object.keys(imagesPerView).forEach((view_name) => {
      zoomFactor[view_name] = 1;
    });

    // Initialize off-thread filter manager
    filterPipeline.init();

    // Fire stage events observers
    resizeObserver.observe(stageContainer);

    return () => {
      resizeObserver.disconnect();
      filterPipeline.destroy();
      if (interactionCooldownTimer) {
        clearTimeout(interactionCooldownTimer);
        interactionCooldownTimer = null;
      }
      clearAnnotationAndInputs();
    };
  });

  let loadCycle = 0;

  // Delegate to ViewRefManager
  function getViewLayer(view_name: string) {
    return viewRefs.getViewLayer(view_name);
  }
  function getImageNode(view_name: string) {
    return viewRefs.getImageNode(view_name);
  }

  function isHtmlImageElement(image: HTMLImageElement | ImageBitmap): image is HTMLImageElement {
    return typeof HTMLImageElement !== "undefined" && image instanceof HTMLImageElement;
  }

  function getCurrentImage(view_name: string): HTMLImageElement | ImageBitmap | undefined {
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
    // Reset flags for the new item
    isReady = false;
    viewRefs.resetViewFlags(keys, enableRenderCache);

    keys.forEach((view_name) => {
      const currentImage = getCurrentImage(view_name);
      if (!currentImage) {
        viewRefs.viewReady[view_name] = true;
        if (Object.values(viewRefs.viewReady).every(Boolean)) {
          isReady = true;
        }
        console.warn(
          `[Canvas2D] Missing current image for view '${view_name}' on item '${selectedItemId}'.`,
        );
        return;
      }

      const onImageReady = () => {
        if (thisLoadCycle !== loadCycle) return;
        viewRefs.registerImageRef(view_name);
        if (viewRefs.scaleOnFirstLoad[view_name]) {
          if (scaleView(view_name)) {
            viewRefs.scaleOnFirstLoad[view_name] = false;
          } else {
            requestAnimationFrame(() => {
              if (thisLoadCycle !== loadCycle) return;
              if (viewRefs.scaleOnFirstLoad[view_name] && scaleView(view_name)) {
                viewRefs.scaleOnFirstLoad[view_name] = false;
                stage?.batchDraw();
              }
            });
          }
        }
        //scaleElements(view_name);
        viewRefs.viewReady[view_name] = true;
        if (Object.values(viewRefs.viewReady).every(Boolean)) {
          isReady = true;
        }
        if (enableRenderCache) cacheImage();
      };
      const onImageError = () => {
        if (thisLoadCycle !== loadCycle) return;
        const failedUrl = isHtmlImageElement(currentImage)
          ? currentImage.currentSrc || currentImage.src || "<unknown>"
          : "<bitmap>";
        console.warn(
          `[Canvas2D] Failed to load image for view '${view_name}' on item '${selectedItemId}': ${failedUrl}`,
        );
        viewRefs.viewReady[view_name] = true;
        if (Object.values(viewRefs.viewReady).every(Boolean)) {
          isReady = true;
        }
      };

      if (isHtmlImageElement(currentImage)) {
        currentImage.onload = onImageReady;
        currentImage.onerror = onImageError;
        // Handle already-loaded images (e.g., from browser cache)
        if (currentImage.complete && currentImage.naturalWidth > 0) {
          onImageReady();
        } else if (currentImage.complete && currentImage.naturalWidth === 0) {
          onImageError();
        }
      } else if (currentImage.width > 0 && currentImage.height > 0) {
        // ImageBitmap is already decoded and renderable.
        onImageReady();
      } else {
        onImageError();
      }
    });

    currentId = selectedItemId;
  }

  function scaleView(view_name: string): boolean {
    const scale = viewRefs.scaleView(
      view_name,
      stageContainer,
      gridSize,
      imagesPerView,
      getCurrentImage,
    );
    if (scale === null) return false;
    zoomFactor[view_name] = scale;
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

  // ********** TOOLS ********** //

  function handleChangeTool() {
    endViewportInteraction();
    const action = computeToolChangeAction(selectedTool);
    cursor = action.cursor;
    if (action.clearCrosshair) crosshairPosition = null;
    if (action.clearBrushCursor) brushCursorState = null;
    if (action.cleanupPolygonPreview) cleanupPolygonPreviewListeners();
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
    const brushRef = viewRefs.maskRefs[viewRef.name];
    if (brushRef) {
      brushRef.beginStroke(pos.x, pos.y);
    }
  }

  function handleBrushPointerMove(view_name: string) {
    const viewLayer = getViewLayer(view_name);
    if (!viewLayer) return;
    const pos = viewLayer.getRelativePointerPosition();
    if (!pos) return;

    const brushRef = viewRefs.maskRefs[view_name];
    if (brushRef) {
      brushRef.updateStroke(pos.x, pos.y);
    }
  }

  function handleBrushPointerUp(view_name: string) {
    activeBrushViewName = null;
    const brushCanvas = viewRefs.maskRefs[view_name];
    if (brushCanvas) {
      brushCanvas.endStroke();
    }
    endViewportInteraction();
  }

  function saveBrushMask(view_name: string) {
    const brushCanvas = viewRefs.maskRefs[view_name];
    if (brushCanvas) {
      const maskData = brushCanvas.getMaskData();
      if (maskData) {
        onNewShapeChange?.(maskData);
      }
    }
  }

  function cleanupAllBrushCanvases() {
    for (const key of Object.keys(viewRefs.maskRefs)) {
      const brushRef = viewRefs.maskRefs[key];
      if (brushRef) {
        brushRef.destroy();
      }
      delete viewRefs.maskRefs[key];
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

    const flush = computeCursorFlushAction(selectedTool);
    if (flush.showCrosshair) {
      updateCrosshairState(position);
    } else {
      crosshairPosition = null;
    }

    if (flush.showBrushCursor) {
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
        for (const key of Object.keys(viewRefs.maskRefs)) {
          viewRefs.maskRefs[key]?.clearCanvas();
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
    const backgroundGroup = viewRefs.getViewGroup(view_name, "background");
    const staticGroup = viewRefs.getViewGroup(view_name, "static");
    const activeGroup = viewRefs.getViewGroup(view_name, "active");
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

  function computeMultiPathBounds(
    mp: DatasetMultiPath,
    imgW: number,
    imgH: number,
  ): { x: number; y: number; width: number; height: number } | null {
    const { coords } = mp.data;
    if (!coords || coords.length < 4) return null;
    let minX = Infinity,
      minY = Infinity,
      maxX = -Infinity,
      maxY = -Infinity;
    for (let i = 0; i < coords.length; i += 2) {
      const px = coords[i] * imgW;
      const py = coords[i + 1] * imgH;
      if (px < minX) minX = px;
      if (py < minY) minY = py;
      if (px > maxX) maxX = px;
      if (py > maxY) maxY = py;
    }
    return { x: minX, y: minY, width: maxX - minX, height: maxY - minY };
  }

  function handleSelectMultiPath(multiPath: DatasetMultiPath) {
    if (multiPath.ui.displayControl.highlighted !== "self") {
      onNewShapeChange?.({
        status: "editing",
        shapeId: multiPath.id,
        top_entity_id: (multiPath.ui.top_entities ?? [])[0]?.id ?? multiPath.data.entity_id,
        viewRef: { name: multiPath.data.view_name, id: multiPath.data.frame_id },
        highlighted: "self",
        type: ShapeType.none,
      });
    }
  }

  function handleClickOnImage(event: PointerEvent, viewRef: Reference) {
    const viewLayer = getViewLayer(viewRef.name);
    if (!viewLayer) return;

    if (selectedTool?.type === ToolType.Pan && event.button === 0) {
      highlightedEntity.value = null;
      return;
    }

    if (selectedTool?.type === ToolType.Pan && event.button !== 1) {
      return;
    }
    const interactionShape = localDraftShape ?? newShape;

    if (
      (interactionShape.status === "none" || interactionShape.status === "editing") &&
      selectedTool?.type !== ToolType.Pan &&
      selectedTool?.type !== ToolType.Brush &&
      selectedTool?.type !== ToolType.Polygon &&
      selectedTool?.type !== ToolType.Polyline
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
    } else if (selectedTool?.type === ToolType.Polyline) {
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
    const viewLayer = getViewLayer(view_name);
    if (!viewLayer) return 1;

    const pointer = stageNode.getRelativePointerPosition();
    const current = {
      x: viewLayer.x(),
      y: viewLayer.y(),
      scaleX: viewLayer.scaleX(),
      scaleY: viewLayer.scaleY(),
    };
    const next = zoomViewTransform(current, direction, pointer.x, pointer.y);

    viewRefs.applyViewTransform(view_name, {
      x: next.x,
      y: next.y,
      scale: next.scaleX,
    });

    return next.scaleX;
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
    const grouped: Record<string, DatasetMask[]> = {};
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

  let multiPathsByView = $derived.by(() => {
    const grouped: Record<string, DatasetMultiPath[]> = {};
    for (const mp of multiPaths) {
      const key = mp.data.view_name;
      if (!grouped[key]) grouped[key] = [];
      grouped[key].push(mp);
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
    if (shape.type === ShapeType.polyline) return shape;
    if (shape.type === ShapeType.mask && "polygonMode" in shape) return shape;
    return null;
  });

  // Lightweight fingerprint that changes when frame identities change.
  let viewFrameIdentity = $derived.by(() => {
    let fp = "";
    for (const [vn, imgs] of Object.entries(imagesPerView)) {
      fp += `${vn}:${imgs[imgs.length - 1]?.id ?? ""};`;
    }
    return fp;
  });

  // Triggers a single batched redraw instead of tracking every annotation property.
  let frameFingerprint = $derived.by(() => {
    return `${viewFrameIdentity}|b${bboxes.length}|m${masks.length}|k${keypoints.length}|p${multiPaths.length}`;
  });

  $effect(() => {
    const s = stage;
    if (!s || !enableRenderCache) return;
    void frameFingerprint;
    requestAnimationFrame(() => s.batchDraw());
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
        (selectedTool?.type === ToolType.Polygon || selectedTool?.type === ToolType.Polyline) &&
        interactionShape.status === "creating" &&
        (interactionShape.type === ShapeType.polygon ||
          interactionShape.type === ShapeType.polyline) &&
        interactionShape.phase === "drawing" &&
        interactionShape.closedPolygons.length > 0;

      if (
        selectedTool?.type === ToolType.Rectangle ||
        selectedTool?.type === ToolType.Polygon ||
        selectedTool?.type === ToolType.Polyline
      ) {
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
      selectPolyline: () => onSelectedToolChange?.(polylineTool),
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

    const isConfirmKey = event.key === "Enter" || confirmKeys.includes(event.key);
    if (
      (isConfirmKey || event.key === "Backspace") &&
      (selectedTool?.type === ToolType.Rectangle ||
        selectedTool?.type === ToolType.Polygon ||
        selectedTool?.type === ToolType.Polyline)
    ) {
      activeToolBridge?.dispatchEvent({
        type: "keyDown",
        key: isConfirmKey ? "Enter" : event.key,
        modifiers: {
          shift: event.shiftKey,
          ctrl: event.ctrlKey,
          alt: event.altKey,
          meta: event.metaKey,
        },
      });
      return;
    }

    // N key: finish current polyline sub-path and start a new one
    if ((event.key === "n" || event.key === "N") && selectedTool?.type === ToolType.Polyline) {
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
  // True for active painting flows in the reduced Pan/Rectangle/Brush architecture.
  let isActivePaintingTool = $derived(selectedTool?.type === ToolType.Brush);

  // Unified tool lifecycle: fallback unsupported tools, reset on shape clear, cleanup on tool switch.
  $effect(() => {
    const currentTool = selectedTool;
    const previousTool = prevSelectedTool;
    const shapeStatus = newShape.status;
    const shouldReset = "shouldReset" in newShape ? newShape.shouldReset : false;

    // Fallback unsupported tools
    if (currentTool && !isSupportedCanvasTool(currentTool)) {
      const fallback = getFallbackCanvasTool();
      if (currentTool !== fallback) {
        onSelectedToolChange?.(fallback);
      }
      prevSelectedTool = currentTool;
      return;
    }

    // Reset when shape explicitly requests it
    if (shapeStatus === "none" && shouldReset) {
      untrack(() => clearAnnotationAndInputs());
      onNewShapeChange?.({ status: "none" });
      prevSelectedTool = currentTool;
      return;
    }

    // Cleanup on tool switch (except brush-to-brush mode toggle)
    const switchingBrushMode =
      previousTool?.type === ToolType.Brush && currentTool?.type === ToolType.Brush;
    if (!switchingBrushMode) {
      untrack(() => clearAnnotationAndInputs());
    }

    prevSelectedTool = currentTool;
  });
  let lastAppliedCanvasSize: number | null = null;
  $effect(() => {
    if (!isReady || !canvasSize) return;
    if (lastAppliedCanvasSize === canvasSize) return;
    for (const view_name of Object.keys(imagesPerView)) {
      scaleView(view_name);
    }
    lastAppliedCanvasSize = canvasSize;
  });
  // Unified tool bridge lifecycle: connect bridge, sync previews, switch FSM.
  $effect(() => {
    const bridge = toolBridge ?? internalToolBridge;
    const currentBridge = untrack(() => activeToolBridge);
    if (bridge !== currentBridge) {
      activeToolBridge = bridge;
      if (bridge) {
        bridge.onRequestSave(handleToolRequestSave);
      }
    }
  });
  $effect(() => {
    const bridge = activeToolBridge;
    if (!bridge) {
      localDraftShape = null;
      return;
    }
    // Sync preview from bridge
    const preview = bridge.preview.value;
    untrack(() => syncToolPreview(preview));
  });
  $effect(() => {
    const bridge = activeToolBridge;
    const tool = selectedTool;
    if (!bridge || !tool) {
      lastBridgeForToolSwitch = bridge;
      lastToolSwitchSignature = null;
      return;
    }
    const signature = getToolSwitchSignature(tool);
    if (bridge === lastBridgeForToolSwitch && signature === lastToolSwitchSignature) {
      return;
    }

    // Keep FSM resets scoped to actual tool changes, not preview updates.
    const fsm = untrack(() => createToolFSMForSelection(tool));
    if (fsm) {
      untrack(() => bridge.switchTool(fsm));
      lastBridgeForToolSwitch = bridge;
      lastToolSwitchSignature = signature;
    }
  });
  // --- Targeted reactive statements (replaces monolithic afterUpdate) ---

  // React to item changes
  $effect(() => {
    if (selectedItemId && currentId !== selectedItemId) {
      loadItem();
    }
  });
  // React to tool changes
  $effect(() => {
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
    if (enableRenderCache && stage && filters) {
      filterPipeline.scheduleFilters(filters, Object.keys(imagesPerView));
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
    onmouseleave={handleMouseLeaveStage}
  >
    <Layer id="background" imageSmoothingEnabled={imageSmoothing} listening={false}>
      {#each Object.entries(imagesPerView) as [view_name, images]}
        <Group id={`bg-${view_name}`} bind:this={viewRefs.backgroundViewRefs[view_name]}>
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

    <Layer id="static" listening={false}>
      {#each Object.entries(imagesPerView) as [view_name, images]}
        {@const currentLoadedImage = images[images.length - 1]}
        {@const currentImage = currentLoadedImage?.element}
        {@const viewRef = { id: currentLoadedImage?.id ?? "", name: view_name }}
        <Group id={`static-${view_name}`} bind:this={viewRefs.staticViewRefs[view_name]}>
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
                  {merge}
                  {onNewShapeChange}
                />
              {/if}
            {/each}
          {/if}

          {@const viewMasks = masksByView[view_name] ?? []}
          {#if (viewMasks.length > 0 || selectedTool?.type === ToolType.Brush) && currentImage}
            <Mask
              bind:this={viewRefs.maskRefs[view_name]}
              {viewRef}
              {currentImage}
              masks={viewMasks}
              {colorScale}
              {selectedTool}
              zoomFactor={zoomFactor[view_name] ?? 1}
              {selectedItemId}
              {brushSettings}
            />
          {/if}

          {#if !isActivePaintingTool}
            {#each multiPathsByView[view_name] ?? [] as multiPath (multiPath.id)}
              {#if !multiPath.ui.displayControl.hidden}
                <MultiPathShape
                  {multiPath}
                  {colorScale}
                  imageWidth={currentImage?.width ?? 0}
                  imageHeight={currentImage?.height ?? 0}
                />
              {/if}
            {/each}
          {/if}

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
          bind:this={viewRefs.activeViewRefs[view_name]}
          dragDistance={0}
          ondragstart={beginViewportInteraction}
          ondragmove={() => {
            viewRefs.syncLinkedViewGroupsFromActive(view_name);
            stage?.batchDraw();
          }}
          ondragend={() => {
            viewRefs.syncLinkedViewGroupsFromActive(view_name);
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
              {#if !bbox.ui.displayControl.editing && (selectedTool?.type === ToolType.Rectangle || selectedTool?.type === ToolType.Pan)}
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
              {:else if bbox.ui.displayControl.editing}
                <BBox2D
                  {bbox}
                  {colorScale}
                  zoomFactor={zoomFactor[view_name] ?? 1}
                  listening={true}
                  imageWidth={currentImage?.width ?? 0}
                  imageHeight={currentImage?.height ?? 0}
                  {merge}
                  {onNewShapeChange}
                />
              {/if}
            {/each}
          {/if}

          {#if !isActivePaintingTool}
            {#each multiPathsByView[view_name] ?? [] as multiPath (multiPath.id)}
              {#if !multiPath.ui.displayControl.hidden && !multiPath.ui.displayControl.editing}
                {@const bounds = computeMultiPathBounds(
                  multiPath,
                  currentImage?.width ?? 0,
                  currentImage?.height ?? 0,
                )}
                {#if bounds}
                  <Rect
                    x={bounds.x}
                    y={bounds.y}
                    width={bounds.width}
                    height={bounds.height}
                    fill="rgba(0,0,0,0.001)"
                    strokeEnabled={false}
                    onpointerdown={(event: Konva.KonvaEventObject<PointerEvent>) => {
                      event.cancelBubble = true;
                      handleSelectMultiPath(multiPath);
                    }}
                  />
                {/if}
              {/if}
            {/each}
          {/if}

          {#if draftPolygon && "viewRef" in draftPolygon && draftPolygon.viewRef?.name === view_name}
            <CreateMultiPath
              {viewRef}
              newShape={draftPolygon}
              zoomFactor={zoomFactor[view_name] ?? 1}
              getRelativePointerOnView={() =>
                getViewLayer(view_name)?.getRelativePointerPosition() ?? null}
              onToolEvent={dispatchPolygonToolEvent}
              isInteracting={isViewportInteracting}
            />
          {/if}

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

    <Layer id="tools" listening={false}>
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
