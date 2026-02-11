<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import Konva from "konva";
  import { nanoid } from "nanoid";
  import { onDestroy, onMount, tick } from "svelte";
  import { Group, Image as KonvaImage, Layer, Stage } from "svelte-konva";
  import { writable, type Writable } from "svelte/store";

  import {
    Annotation,
    BBox,
    Mask,
    SaveShapeType,
    type BrushSelectionTool,
    type ImagesPerView,
    type KeypointsTemplate,
    type LabeledPointTool,
    type Reference,
    type SegmentationResult,
    type SelectionTool,
    type Shape,
    type Vertex,
  } from "@pixano/core";
  import { cn } from "@pixano/core/src";
  import {
    pixanoInferenceToValidateTrackingMasks,
    pixanoInferenceTracking,
  } from "@pixano/core/src/components/pixano_inference_segmentation/inference";
  import {
    addSmartPointTool,
    brushDrawTool,
    brushEraseTool,
    rectangleTool,
    removeSmartPointTool,
    smartRectangleTool,
  } from "@pixano/dataset-item-workspace/src/lib/settings/selectionTools";
  import {
    brushSettings as brushSettingsStore,
    selectedTool as selectedToolStore,
  } from "@pixano/dataset-item-workspace/src/lib/stores/datasetItemWorkspaceStores";
  import type { Filters } from "@pixano/dataset-item-workspace/src/lib/types/datasetItemWorkspaceTypes";
  import type { Box, InteractiveImageSegmenterOutput, LabeledClick } from "@pixano/models";
  import { convertSegmentsToSVG, generatePolygonSegments } from "@pixano/models/src/mask_utils";

  import { addMask, clearCurrentAnn, findOrCreateCurrentMask } from "./api/boundingBoxesApi";
  import { clearParsedCache, convertPointToSvg, runLengthEncode } from "./api/maskApi";
  import { resizeStroke } from "./api/rectangleApi";
  import BrushCanvas from "./components/BrushCanvas.svelte";
  import CreateKeypoint from "./components/CreateKeypoints.svelte";
  import CreatePolygon from "./components/CreatePolygon.svelte";
  import CreateRectangle from "./components/CreateRectangle.svelte";
  import PolygonGroup from "./components/PolygonGroup.svelte";
  import Rectangle from "./components/Rectangle.svelte";
  import ShowKeypoints from "./components/ShowKeypoint.svelte";
  import {
    INPUTPOINT_RADIUS,
    // INPUTRECT_STROKEWIDTH,
    // BBOX_STROKEWIDTH,
    // MASK_STROKEWIDTH,
    POINT_SELECTION,
  } from "./lib/constants";
  import { equalizeHistogram } from "./lib/utils/equalizeHistogram";
  import { FilterManager } from "./lib/workers/filterManager";
  import type { FilterParams } from "./lib/workers/filterWorker";
  import { createPanTool, ToolType } from "./tools";

  interface BrushCanvasRef {
    beginStroke(x: number, y: number): void;
    updateStroke(x: number, y: number): void;
    endStroke(): void;
    getMaskData(): Shape | null;
    clearCanvas(): void;
    destroy(): void;
  }

  // Exports
  export let selectedItemId: string;
  export let masks: Mask[];
  export let bboxes: BBox[];
  export let keypoints: KeypointsTemplate[] = [];
  export let selectedKeypointTemplate: KeypointsTemplate | undefined = undefined;
  export let currentAnn: InteractiveImageSegmenterOutput | null = null;
  export let selectedTool: SelectionTool;
  export let newShape: Shape;
  export let imagesPerView: ImagesPerView;
  export let colorScale: (value: string) => string;
  export let isVideo: boolean = false;
  export let imageSmoothing: boolean = true;
  export let merge: (ann: Annotation) => void = () => {
    return;
  };
  export let pixanoInferenceSegmentation: (
    viewRef: Reference,
    points: LabeledClick[],
    box: Box,
  ) => Promise<Mask | undefined>;

  // Image settings
  export let filters: Writable<Filters> = writable<Filters>();
  export let canvasSize: number = 0;

  let isReady = false;

  let numberOfBBoxes: number;
  let prevSelectedTool: SelectionTool;
  let zoomFactor: Record<string, number> = {}; // {view_name: zoomFactor}

  let lastInputViewRef: Reference;

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
  let pendingBrushMask: {
    rle: { counts: number[]; size: [number, number] };
    maskId: string;
    viewName: string;
  } | null = null;

  // True for Brush tool AND all smart/AI segmentation tools
  $: isActivePaintingTool = selectedTool?.type === ToolType.Brush || selectedTool?.isSmart === true;

  $: {
    if (
      !prevSelectedTool?.isSmart ||
      !selectedTool?.isSmart ||
      (newShape.status === "none" && newShape.shouldReset)
    ) {
      // Capture AI mask before clearing if switching to brush tool
      if (
        prevSelectedTool?.isSmart &&
        selectedTool?.type === ToolType.Brush &&
        currentAnn?.output?.rle
      ) {
        const rle = currentAnn.output.rle;
        const counts = Array.isArray(rle.counts) ? rle.counts : [];
        pendingBrushMask = {
          rle: { counts, size: rle.size as [number, number] },
          maskId: currentAnn.id,
          viewName: currentAnn.viewRef.name,
        };
      }
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

  let timerId: ReturnType<typeof setTimeout>;

  // References to HTML Elements
  let stageContainer: HTMLElement;

  // References to Konva Elements
  let stage: Konva.Stage;
  let toolsLayer: Konva.Layer;
  let highlighted_point: Konva.Text = null;
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

  // React to annotation validation
  $: if (currentAnn && currentAnn.validated) {
    validateCurrentAnn();
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
      console.log("Canvas2D.scaleView - Error: Cannot scale");
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

  // Unused ... We could remove ?
  // function scaleElements(view_name: string) {
  //   const viewLayer: Konva.Layer = stage.findOne(`#${view_name}`);
  //   if (!viewLayer) {
  //     console.log("Canvas2D.scaleElements - Error: Cannot scale");
  //     return;
  //   }

  //   const zoom = zoomFactor[view_name];

  //   const scaleCircle = (circle: Konva.Circle) => {
  //     circle.radius(INPUTPOINT_RADIUS / zoom);
  //     circle.strokeWidth(INPUTPOINT_STROKEWIDTH / zoom);
  //   };

  //   const scaleRect = (rect: Konva.Rect, strokeWidth: number) => {
  //     rect.strokeWidth(strokeWidth / zoom);
  //   };

  //   // Scale input points
  //   const inputGroup: Konva.Group = viewLayer.findOne("#input");
  //   if (inputGroup) {
  //     inputGroup.children.forEach((point) => {
  //       if (point instanceof Konva.Circle) {
  //         scaleCircle(point);
  //       } else if (point instanceof Konva.Rect) {
  //         scaleRect(point, INPUTRECT_STROKEWIDTH);
  //       }
  //     });
  //   }

  //   // Scale bboxes
  //   const bboxGroup: Konva.Group = viewLayer.findOne("#bboxes");
  //   if (bboxGroup) {
  //     bboxGroup.children.forEach((bboxKonva) => {
  //       if (bboxKonva instanceof Konva.Group) {
  //         bboxKonva.children.forEach((bboxElement) => {
  //           if (bboxElement instanceof Konva.Rect) {
  //             scaleRect(bboxElement, BBOX_STROKEWIDTH);
  //           } else if (bboxElement instanceof Konva.Label) {
  //             bboxElement.scale({
  //               x: 1 / zoom,
  //               y: 1 / zoom,
  //             });
  //           }
  //         });
  //       }
  //     });
  //   }

  //   // Scale masks
  //   const scaleMaskGroup = (maskGroup: Konva.Group) => {
  //     maskGroup.children.forEach((maskKonva) => {
  //       if (maskKonva instanceof Konva.Shape) {
  //         maskKonva.strokeWidth(MASK_STROKEWIDTH / zoom);
  //       }
  //     });
  //   };

  //   const maskGroup: Konva.Group = viewLayer.findOne("#masks");
  //   if (maskGroup) {
  //     scaleMaskGroup(maskGroup);
  //   }

  //   const currentMaskGroup = findOrCreateCurrentMask(view_name, stage);
  //   if (currentMaskGroup) {
  //     scaleMaskGroup(currentMaskGroup);
  //   }

  //   // Scale keypoints //TODO?
  //   // const scaleKptCircle = (circle: Konva.Circle) => {
  //   //   circle.radius(INPUTPOINT_RADIUS / zoom);
  //   //   circle.strokeWidth(INPUTPOINT_STROKEWIDTH / zoom);
  //   // };
  // }

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

  function findViewName(shape: Konva.Shape): string {
    let view_name: string;
    shape.getAncestors().forEach((node) => {
      if (node instanceof Konva.Layer) {
        view_name = node.id();
      }
    });
    return view_name;
  }

  // ********** BOUNDING BOXES AND MASKS ********** //

  // launch tracking on validate
  $: if (isVideo && $pixanoInferenceTracking.mustValidate && $pixanoInferenceTracking.validated) {
    if (lastInputViewRef != undefined) {
      void updateCurrentMask(lastInputViewRef);
    }
  }

  async function updateCurrentMask(viewRef: Reference) {
    let results: SegmentationResult = null;

    const points = getInputPoints(viewRef.name);
    const box = getInputRect(viewRef.name);
    const currentImage = getCurrentImage(viewRef.name);

    // Remote inference via pixano-inference server
    if (
      (isVideo &&
        (($pixanoInferenceTracking.mustValidate && $pixanoInferenceTracking.validated) ||
          !$pixanoInferenceTracking.mustValidate)) ||
      !isVideo
    ) {
      const pixinf_res = await pixanoInferenceSegmentation(viewRef, points, box);
      $pixanoInferenceTracking.validated = false;
      if (pixinf_res) {
        const maskPolygons = generatePolygonSegments(
          pixinf_res.data.counts as number[],
          currentImage.height,
        );
        const masksSVG = convertSegmentsToSVG(maskPolygons);

        results = {
          masksImageSVG: masksSVG,
          rle: {
            counts: pixinf_res.data.counts,
            size: pixinf_res.data.size,
            id: pixinf_res.id,
            ref_name: pixinf_res.table_info.name,
          },
        };
      }
    }

    if (results) {
      const currentMaskGroup = findOrCreateCurrentMask(viewRef.name, stage);
      const image = getImageNode(viewRef.name);

      // always clean existing masks before adding a new currentAnn
      currentMaskGroup.removeChildren();

      currentAnn = {
        id: nanoid(10),
        viewRef,
        label: "",
        output: results,
        input_points: points,
        input_box: box,
        validated: false,
      };
      addMask(
        currentAnn.id,
        currentAnn.output.masksImageSVG,
        true,
        1.0,
        "#FF0050",
        currentMaskGroup,
        image,
        viewRef.name,
        stage,
        zoomFactor,
      );
    }
  }

  function validateSmartMask() {
    if (!currentAnn?.output) return;
    const currentImage = getCurrentImage(currentAnn.viewRef.name);
    newShape = {
      masksImageSVG: currentAnn.output.masksImageSVG,
      rle: currentAnn.output.rle,
      type: SaveShapeType.mask,
      viewRef: currentAnn.viewRef,
      itemId: selectedItemId,
      imageWidth: currentImage.width,
      imageHeight: currentImage.height,
      status: "saving",
    };
  }

  // ********** CURRENT ANNOTATION ********** //

  function validateCurrentAnn() {
    if (currentAnn.validated) {
      const currentMaskGroup = findOrCreateCurrentMask(currentAnn.viewRef.name, stage);
      if (currentMaskGroup) currentMaskGroup.destroyChildren();
      if (highlighted_point) unhighlightInputPoint(highlighted_point);
      clearInputs(currentAnn.viewRef.name);
      currentAnn = null;
    }
  }

  // ********** TOOLS ********** //

  function handleChangeTool() {
    //make sure tools layer is on front
    if (toolsLayer) toolsLayer.moveToTop();

    // Update the behavior of the canvas stage based on the selected tool
    // You can add more cases for different tools as needed
    switch (selectedTool.type) {
      case ToolType.PointSelection:
        displayInputPointTool(selectedTool);
        displayCrosshair(selectedTool);
        break;
      case ToolType.Rectangle:
        displayCrosshair(selectedTool);
        // Enable box creation or change cursor style
        break;
      case ToolType.Polygon:
        displayCrosshair(selectedTool);
        break;
      case ToolType.Keypoint:
        displayCrosshair(selectedTool);
        // Enable keypoint creation or change cursor style
        break;
      case ToolType.Delete:
        clearAnnotationAndInputs();
        displayInputDeleteTool(selectedTool);
        break;
      case ToolType.Pan:
        displayPanTool(selectedTool);
        // Enable box creation or change cursor style
        break;
      case ToolType.Classification:
        displayClassificationTool(selectedTool);
        break;
      case ToolType.Brush:
        displayBrushTool(selectedTool);
        break;

      default:
        // Reset or disable any specific behavior
        break;
    }
  }

  function clearInputs(view_name: string) {
    const viewLayer = getViewLayer(view_name);
    if (viewLayer) {
      const inputGroup: Konva.Group = viewLayer.findOne("#input");
      inputGroup.destroyChildren();
    }
  }

  // ********** POLYGON TOOL ********** //

  function drawPolygonPoints(viewRef: Reference) {
    if (newShape?.status === "saving") return;
    const viewLayer = getViewLayer(viewRef.name);
    const cursorPositionOnImage = viewLayer.getRelativePointerPosition();
    const x = Math.round(cursorPositionOnImage.x);
    const y = Math.round(cursorPositionOnImage.y);

    // If in editing phase, start a new polygon
    if (
      newShape.status === "creating" &&
      newShape.type === SaveShapeType.mask &&
      newShape.phase === "editing"
    ) {
      newShape = {
        ...newShape,
        phase: "drawing",
        points: [{ x, y, id: 0 }],
      };
      return;
    }

    const oldPoints =
      newShape.status === "creating" && newShape.type === SaveShapeType.mask ? newShape.points : [];
    const closedPolygons =
      newShape.status === "creating" && newShape.type === SaveShapeType.mask
        ? newShape.closedPolygons
        : [];
    newShape = {
      status: "creating",
      type: SaveShapeType.mask,
      points: [...oldPoints, { x, y, id: oldPoints.length || 0 }],
      closedPolygons,
      phase: "drawing",
      viewRef,
    };
  }

  // ********** KEY_POINT TOOL ********** //

  function dragInputKeyPointRectMove(viewRef: Reference) {
    if (selectedTool?.type === ToolType.Keypoint && newShape.status !== "saving") {
      const viewLayer = getViewLayer(viewRef.name);

      const pos = viewLayer.getRelativePointerPosition();
      const x =
        newShape.status === "creating" && newShape.type === SaveShapeType.keypoints
          ? newShape.x
          : pos.x;
      const y =
        newShape.status === "creating" && newShape.type === SaveShapeType.keypoints
          ? newShape.y
          : pos.y;
      const width = pos.x - x;
      const height = pos.y - y;
      newShape = {
        status: "creating",
        type: SaveShapeType.keypoints,
        x,
        y,
        width,
        height,
        viewRef,
        keypoints: selectedKeypointTemplate,
      };
    }
  }

  function dragKeyPointInputRectEnd(viewRef: Reference) {
    if (selectedTool?.type === ToolType.Keypoint) {
      const viewLayer = getViewLayer(viewRef.name);
      const rect: Konva.Rect = stage.findOne("#move-keyPoints-group");
      if (rect && newShape.status === "creating" && newShape.type === SaveShapeType.keypoints) {
        const vertices = newShape.keypoints.vertices.map((vertex) => {
          if (newShape.status === "creating" && newShape.type === SaveShapeType.keypoints)
            return {
              ...vertex,
              x: newShape.x + vertex.x * newShape.width,
              y: newShape.y + vertex.y * newShape.height,
            } as Required<Vertex>;
        });
        newShape = {
          status: "saving",
          type: SaveShapeType.keypoints,
          viewRef,
          itemId: selectedItemId,
          imageWidth: getCurrentImage(viewRef.name).width,
          imageHeight: getCurrentImage(viewRef.name).height,
          keypoints: { ...newShape.keypoints, vertices },
        };
        viewLayer.off("pointermove");
        viewLayer.off("pointerup");
      }
    }
  }

  // ********** PAN TOOL ********** //

  function displayPanTool(tool: SelectionTool) {
    if (toolsLayer) {
      //clean other tools
      //TODO: etre générique sur l'ensemble des outils != Pan
      const pointer = stage.findOne(`#${POINT_SELECTION}`);
      if (pointer) pointer.destroy();
      const crossline = stage.findOne("#crossline");
      if (crossline) crossline.destroy();
      if (!highlighted_point) {
        stage.container().style.cursor = tool.cursor;
      }
      // deactivate drag on input points
      toggleInputPointDrag(false);
    }
  }

  // ********** CLASSIFICATION TOOL ********** //

  function displayClassificationTool(tool: SelectionTool) {
    if (toolsLayer) {
      //clean other tools
      //TODO: etre générique sur l'ensemble des outils != Pan
      const pointer = stage.findOne(`#${POINT_SELECTION}`);
      if (pointer) pointer.destroy();
      const crossline = stage.findOne("#crossline");
      if (crossline) crossline.destroy();
      if (!highlighted_point) {
        stage.container().style.cursor = tool.cursor;
      }
      // deactivate drag on input points
      toggleInputPointDrag(false);
    }
  }

  // ********** BRUSH TOOL ********** //

  function displayBrushTool(tool: SelectionTool) {
    if (toolsLayer) {
      // Clean other tools
      const pointer = stage.findOne(`#${POINT_SELECTION}`);
      if (pointer) pointer.destroy();

      // Show crosshair like other drawing tools
      displayCrosshair(tool);

      // Hide native cursor, we'll show a custom brush cursor
      stage.container().style.cursor = "none";

      // Deactivate drag on input points
      toggleInputPointDrag(false);
    }
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
        radius: $brushSettingsStore.brushRadius,
        stroke: cursorColor,
        strokeWidth: 2,
        fill: mode === "draw" ? "rgba(0, 200, 0, 0.1)" : "rgba(200, 0, 0, 0.1)",
        listening: false,
      });
      toolsLayer.add(brushCursor);
    }

    brushCursor.radius($brushSettingsStore.brushRadius);
    brushCursor.stroke(cursorColor);
    brushCursor.fill(mode === "draw" ? "rgba(0, 200, 0, 0.1)" : "rgba(200, 0, 0, 0.1)");
    brushCursor.x(mousePos.x);
    brushCursor.y(mousePos.y);
    brushCursor.show();
  }

  $: if (brushCursor && selectedTool?.type === ToolType.Brush) {
    brushCursor.radius($brushSettingsStore.brushRadius);
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

  function handleBrushPointerDown(viewRef: Reference) {
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
    pendingBrushMask = null;
  }

  // ********** INPUT POINTS TOOL ********** //

  function displayInputPointTool(tool: LabeledPointTool) {
    if (toolsLayer) {
      //clean other tools
      //TODO: etre générique sur l'ensemble des outils != Point
      const crossline = toolsLayer.findOne("#crossline");
      if (crossline) crossline.destroy();

      const pointer = findOrCreateInputPointPointer(tool.type);
      pointer.text(tool.label === 1 ? "+" : "\u2212");
      if (!highlighted_point) {
        stage.container().style.cursor = tool.cursor;
      }
      // activate drag on input points
      toggleInputPointDrag(true);
    }
  }

  function updateInputPointStage(mousePos: Konva.Vector2d) {
    const pointer = findOrCreateInputPointPointer(selectedTool.type);
    const scale = stage.scaleX();
    const pointerScale = Math.max(1, 1 / scale);
    pointer.scaleX(pointerScale);
    pointer.scaleY(pointerScale);
    const indicatorOffset = 16 * pointerScale;
    pointer.x(mousePos.x - indicatorOffset);
    pointer.y(mousePos.y - indicatorOffset);
  }

  function findOrCreateInputPointPointer(id: string, view_name: string = null): Konva.Text {
    let pointer: Konva.Text = stage.findOne(`#${id}`);
    if (!pointer) {
      let zoomF = 1.0; // in some cases we aren't in a view, so we use default scaling
      if (view_name) zoomF = zoomFactor[view_name];
      pointer = new Konva.Text({
        id,
        x: 0,
        y: 0,
        text: "+",
        fontSize: (INPUTPOINT_RADIUS * 4) / zoomF,
        fontStyle: "bold",
        fill: "white",
        stroke: "black",
        strokeWidth: 1 / zoomF,
        offsetX: (INPUTPOINT_RADIUS * 2) / zoomF,
        offsetY: (INPUTPOINT_RADIUS * 2) / zoomF,
        visible: false,
        listening: false,
        opacity: 0.9,
      });
      toolsLayer.add(pointer);
    }
    return pointer;
  }

  function getInputPoints(view_name: string): Array<LabeledClick> {
    //get points as Array<LabeledClick>
    const points: Array<LabeledClick> = [];
    const viewLayer = getViewLayer(view_name);
    const inputGroup: Konva.Group = viewLayer.findOne("#input");
    for (const pt of inputGroup.children) {
      if (pt instanceof Konva.Text) {
        const lblclick: LabeledClick = {
          x: pt.x(),
          y: pt.y(),
          label: parseInt(pt.name()),
        };
        points.push(lblclick);
      }
    }
    return points;
  }

  function toggleInputPointDrag(toggle: boolean) {
    const input_groups = stage.find("#input");
    for (const input_group of input_groups) {
      for (const node of (input_group as Konva.Group).children) {
        if (node instanceof Konva.Text) {
          node.listening(toggle);
        }
      }
    }
  }

  function dragInputPointEnd() {
    stage.container().style.cursor = "grab";
  }

  function dragInputPointMove(drag_point: Konva.Text, viewRef: Reference) {
    stage.container().style.cursor = "grabbing";

    const image = getImageNode(viewRef.name);
    const img_size = image.getSize();
    if (drag_point.x() < 0) {
      drag_point.x(0);
    } else if (drag_point.x() > img_size.width) {
      drag_point.x(img_size.width);
    }
    if (drag_point.y() < 0) {
      drag_point.y(0);
    } else if (drag_point.y() > img_size.height) {
      drag_point.y(img_size.height);
    }
    lastInputViewRef = viewRef;

    // new currentAnn on new location
    clearTimeout(timerId); // reinit timer on each move move
    timerId = setTimeout(() => updateCurrentMask(viewRef), 50); // delay before predict to spare CPU
  }

  function highlightInputPoint(hl_point: Konva.Text, view_name: string) {
    const pointer = findOrCreateInputPointPointer(selectedTool.type, view_name);
    pointer.hide();
    hl_point.fontSize((1.5 * INPUTPOINT_RADIUS * 4) / zoomFactor[view_name]);
    hl_point.offsetX((1.5 * INPUTPOINT_RADIUS * 2) / zoomFactor[view_name]);
    hl_point.offsetY((1.5 * INPUTPOINT_RADIUS * 2) / zoomFactor[view_name]);
    highlighted_point = hl_point;
    stage.container().style.cursor = "grab";
  }

  function unhighlightInputPoint(hl_point: Konva.Text, view_name: string = null) {
    const pointer = findOrCreateInputPointPointer(selectedTool.type, view_name);
    pointer.show();
    if (!view_name) {
      view_name = findViewName(hl_point);
    }
    hl_point.fontSize((INPUTPOINT_RADIUS * 4) / zoomFactor[view_name]);
    hl_point.offsetX((INPUTPOINT_RADIUS * 2) / zoomFactor[view_name]);
    hl_point.offsetY((INPUTPOINT_RADIUS * 2) / zoomFactor[view_name]);
    highlighted_point = null;
    stage.container().style.cursor = selectedTool.cursor;
    stage.batchDraw();
  }

  // ********** CROSSHAIR TOOL ********** //

  function displayCrosshair(tool: SelectionTool) {
    if (toolsLayer) {
      //clean other tools
      const pointer = stage.findOne(`#${POINT_SELECTION}`);
      if (pointer && tool.type !== ToolType.PointSelection) pointer.destroy();
      if (!highlighted_point) {
        stage.container().style.cursor = tool.cursor;
      }
      // activate drag on input points
      toggleInputPointDrag(true);
    }
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

  function getInputRect(view_name: string): Box {
    //get box as Box
    let box: Box = null;
    const viewLayer = getViewLayer(view_name);
    const rect: Konva.Rect = viewLayer.findOne("#drag-rect");
    if (rect) {
      //need to convert rect pos / size to topleft/bottomright
      const size = rect.size();
      const pos = rect.position();
      box = {
        x: pos.x,
        y: pos.y,
        width: size.width,
        height: size.height,
      };
    }
    return box;
  }

  function dragInputRectMove(viewRef: Reference) {
    if (selectedTool?.type === ToolType.Rectangle) {
      const viewLayer = getViewLayer(viewRef.name);

      const pos = viewLayer.getRelativePointerPosition();
      const x =
        newShape.status === "creating" && newShape.type === SaveShapeType.bbox ? newShape.x : pos.x;
      const y =
        newShape.status === "creating" && newShape.type === SaveShapeType.bbox ? newShape.y : pos.y;
      newShape = {
        status: "creating",
        type: SaveShapeType.bbox,
        x,
        y,
        width: pos.x - x,
        height: pos.y - y,
        viewRef,
      };
    }
  }

  async function dragInputRectEnd(viewRef: Reference) {
    if (selectedTool?.type === ToolType.Rectangle) {
      const viewLayer = getViewLayer(viewRef.name);
      const rect: Konva.Rect = stage.findOne("#drag-rect");
      if (rect) {
        const { width, height } = rect.size();
        if (width === 0 || height === 0) {
          //rect with area = 0 -> delete it
          newShape = { status: "none" };
        } else {
          if (!selectedTool.isSmart) {
            const correctedRect = rect.getClientRect({
              skipTransform: false,
              skipShadow: true,
              skipStroke: true,
              relativeTo: viewLayer,
            });
            // Keep in "creating" state so user can adjust before pressing Enter
            newShape = {
              status: "creating",
              type: SaveShapeType.bbox,
              x: correctedRect.x,
              y: correctedRect.y,
              width: correctedRect.width,
              height: correctedRect.height,
              viewRef,
            };
            // Attach Transformer for resize/move
            bboxEditable = true;
            const tr: Konva.Transformer = stage.findOne("#transformer");
            if (tr) {
              tr.nodes([rect]);
              tr.getLayer()?.batchDraw();
            }
            // Sync Transformer changes back to newShape so Svelte doesn't revert them
            rect.on("transform.creation", () => {
              resizeStroke(rect);
            });
            rect.on("transformend.creation dragend.creation", () => {
              newShape = {
                status: "creating",
                type: SaveShapeType.bbox,
                x: rect.x(),
                y: rect.y(),
                width: rect.width(),
                height: rect.height(),
                viewRef,
              };
            });
          }
          if (selectedTool.isSmart) {
            lastInputViewRef = viewRef;
            await updateCurrentMask(viewRef);
          }
        }
        viewLayer.off("pointermove");
        viewLayer.off("pointerup");
      }
      if (selectedTool.isSmart && !$pixanoInferenceTracking.mustValidate) {
        rect.destroy();
      }
    }
  }

  function validateBBox(viewRef: Reference) {
    const viewLayer = getViewLayer(viewRef.name);
    const rect: Konva.Rect = stage.findOne("#drag-rect");
    if (!rect) return;

    // Read final position after any Transformer edits
    const correctedRect = rect.getClientRect({
      skipTransform: false,
      skipShadow: true,
      skipStroke: true,
      relativeTo: viewLayer,
    });

    // Clean up creation listeners and detach Transformer
    rect.off("transform.creation");
    rect.off("transformend.creation");
    rect.off("dragend.creation");
    bboxEditable = false;
    const tr: Konva.Transformer = stage.findOne("#transformer");
    if (tr) tr.nodes([]);

    newShape = {
      status: "saving",
      attrs: {
        x: correctedRect.x,
        y: correctedRect.y,
        width: correctedRect.width,
        height: correctedRect.height,
      },
      type: SaveShapeType.bbox,
      viewRef,
      itemId: selectedItemId,
      imageWidth: getCurrentImage(viewRef.name).width,
      imageHeight: getCurrentImage(viewRef.name).height,
    };
  }

  function validatePolygon(viewRef: Reference) {
    if (
      newShape.status !== "creating" ||
      newShape.type !== SaveShapeType.mask ||
      newShape.phase !== "editing"
    )
      return;
    const currentImage = getCurrentImage(viewRef.name);
    const svg = newShape.closedPolygons.map((polygon) => convertPointToSvg(polygon));
    const counts = runLengthEncode(svg, currentImage.width, currentImage.height);
    newShape = {
      status: "saving",
      masksImageSVG: svg,
      rle: { counts, size: [currentImage.height, currentImage.width] },
      type: SaveShapeType.mask,
      viewRef,
      itemId: selectedItemId,
      imageWidth: currentImage.width,
      imageHeight: currentImage.height,
    };
  }

  // ********** INPUT DELETE TOOL ********** //

  function displayInputDeleteTool(tool: SelectionTool) {
    if (toolsLayer) {
      //clean other tools
      //TODO: etre générique sur l'ensemble des outils != DELETE
      const pointer = stage.findOne(`#${POINT_SELECTION}`);
      if (pointer) pointer.destroy();
      const crossline = stage.findOne("#crossline");
      if (crossline) crossline.destroy();

      if (!highlighted_point) {
        stage.container().style.cursor = tool.cursor;
      }
      // deactivate drag on input points
      toggleInputPointDrag(false);
    }
  }

  function clearAnnotationAndInputs() {
    if (!stage) return;
    for (const view_name of Object.keys(imagesPerView)) {
      clearInputs(view_name);
      clearCurrentAnn(view_name, stage, selectedTool);
      pixanoInferenceToValidateTrackingMasks.set([]);
    }
    if (selectedTool) {
      stage.container().style.cursor = selectedTool.cursor;
    }
    const pointer: Konva.Text = stage.findOne(`#${POINT_SELECTION}`);
    if (pointer) pointer.destroy();
    const crossline = toolsLayer?.findOne("#crossline");
    if (crossline) crossline.destroy();
    cleanupBrushCursor();
    // Only clear brush canvases after the user confirms (shouldReset) or
    // when leaving the brush tool — NOT while the save form is open.
    if (newShape.status !== "saving") {
      if (selectedTool?.type !== ToolType.Brush || newShape.shouldReset) {
        for (const key of Object.keys(brushCanvasRefs)) {
          brushCanvasRefs[key]?.clearCanvas();
        }
      }
      if (selectedTool?.type !== ToolType.Brush) {
        pendingBrushMask = null;
      }
    }
    currentAnn = null;
  }

  // ********** MOUSE EVENTS ********** //

  function handleMouseMoveStage() {
    const position = stage.getRelativePointerPosition();

    // Update tools states
    if (selectedTool?.type === ToolType.PointSelection) {
      updateInputPointStage(position);
    }

    if (
      [
        ToolType.Rectangle,
        ToolType.Polygon,
        ToolType.Keypoint,
        ToolType.PointSelection,
        ToolType.Brush,
      ].includes(selectedTool?.type)
    ) {
      updateCrosshairState(position);
    }

    // Update brush cursor and brush stroke
    if (selectedTool?.type === ToolType.Brush) {
      updateBrushCursor(position);
      // Update brush stroke for all views (the active one will handle it)
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

  function handlePointerUpOnImage(viewRef: Reference) {
    const viewLayer = getViewLayer(viewRef.name);
    viewLayer.draggable(false);
    viewLayer.off("dragend dragmove");
    if (selectedTool?.type === ToolType.Polygon) {
      drawPolygonPoints(viewRef);
    }

    if (selectedTool?.type === ToolType.Brush) {
      handleBrushPointerUp(viewRef.name);
    }

    if (highlighted_point) {
      //hack to unhiglight when we drag while predicting...
      //try to determine if we are still on highlighted point
      //Note: could be better, but usually it will work
      const pos = viewLayer.getRelativePointerPosition();
      const hl_pos = highlighted_point.position();
      if (pos.x !== hl_pos.x || pos.y !== hl_pos.y)
        unhighlightInputPoint(highlighted_point, viewRef.name);
    }
  }

  function handleDoubleClickOnImage(view_name: string) {
    // put double-clickd view on top of views
    const viewLayer = getViewLayer(view_name);
    viewLayer.moveToTop();
    //keeps tools on top
    toolsLayer.moveToTop();
  }

  async function handleClickOnImage(event: PointerEvent, viewRef: Reference) {
    const viewLayer = getViewLayer(viewRef.name);

    if (
      (newShape.status === "none" || newShape.status === "editing") &&
      selectedTool?.type !== ToolType.Brush
    ) {
      newShape = {
        status: "editing",
        viewRef,
        type: "none",
        shapeId: null,
        highlighted: "all",
      };
    }
    // Perform tool action if any active tool
    // For convenience: bypass tool on mouse middle-button click
    if (selectedTool?.type === ToolType.Pan || event.button === 1) {
      viewLayer.draggable(true);
      viewLayer.on("dragmove", handleMouseMoveStage);
      viewLayer.on("dragend", () => handleDragEndOnView(viewRef.name));
    } else if (selectedTool?.type === ToolType.PointSelection) {
      const clickOnViewPos = viewLayer.getRelativePointerPosition();

      //add Konva Point
      const input_point = new Konva.Text({
        name: `${selectedTool.label}`,
        x: clickOnViewPos.x,
        y: clickOnViewPos.y,
        text: selectedTool.label === 1 ? "+" : "\u2212",
        fontSize: (INPUTPOINT_RADIUS * 4) / zoomFactor[viewRef.name],
        fontStyle: "bold",
        fill: "white",
        stroke: "black",
        strokeWidth: 1 / zoomFactor[viewRef.name],
        offsetX: (INPUTPOINT_RADIUS * 2) / zoomFactor[viewRef.name],
        offsetY: (INPUTPOINT_RADIUS * 2) / zoomFactor[viewRef.name],
        visible: true,
        listening: true,
        opacity: 0.9,
        draggable: true,
      });
      input_point.on("pointerenter", (event) =>
        highlightInputPoint(event.target as Konva.Text, viewRef.name),
      );
      input_point.on("pointerout", (event) =>
        unhighlightInputPoint(event.target as Konva.Text, viewRef.name),
      );
      input_point.on(
        "dragmove",
        (event) => void dragInputPointMove(event.target as Konva.Text, viewRef),
      );
      input_point.on("dragend", () => dragInputPointEnd());
      const inputGroup: Konva.Group = viewLayer.findOne("#input");
      inputGroup.add(input_point);
      inputGroup.moveToTop(); //ensure input points stay over other groups
      highlightInputPoint(input_point, viewRef.name);
      lastInputViewRef = viewRef;
      await updateCurrentMask(viewRef);
    } else if (selectedTool?.type === ToolType.Brush) {
      handleBrushPointerDown(viewRef);
      viewLayer.on("pointermove.brush", () => handleBrushPointerMove(viewRef.name));
      viewLayer.on("pointerup.brush", () => handleBrushPointerUp(viewRef.name));
    } else if (selectedTool?.type === ToolType.Rectangle && !bboxEditable) {
      viewLayer.on("pointermove", () => dragInputRectMove(viewRef));
      viewLayer.on("pointerup", () => void dragInputRectEnd(viewRef));
    } else if (selectedTool?.type === ToolType.Keypoint) {
      viewLayer.on("pointermove", () => dragInputKeyPointRectMove(viewRef));
      viewLayer.on("pointerup", () => void dragKeyPointInputRectEnd(viewRef));
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
    //scaleElements(view_name);

    // Keep highlighted point scaling
    if (highlighted_point) highlightInputPoint(highlighted_point, view_name);
  }

  // ********** KEY EVENTS ********** //

  async function handleKeyDown(event: KeyboardEvent) {
    const activeElement = document.activeElement;
    if (
      activeElement instanceof HTMLInputElement ||
      activeElement instanceof HTMLTextAreaElement ||
      activeElement?.getAttribute("contenteditable") === "true"
    ) {
      return; // Ignore shortcut when typing text
    }

    if (event.key === "Escape") {
      // Polygon: if drawing a 2nd+ polygon, discard only in-progress and return to editing
      if (
        selectedTool?.type === ToolType.Polygon &&
        newShape.status === "creating" &&
        newShape.type === SaveShapeType.mask &&
        newShape.phase === "drawing" &&
        newShape.closedPolygons?.length > 0
      ) {
        newShape = { ...newShape, points: [], phase: "editing" };
        return;
      }

      // If brush tool is active, clean up before switching to pan
      if (selectedTool?.type === ToolType.Brush) {
        cleanupAllBrushCanvases();
      }
      // Clean up creation listeners and detach transformer (for bbox editing)
      const dragRect: Konva.Rect = stage?.findOne("#drag-rect");
      if (dragRect) {
        dragRect.off("transform.creation");
        dragRect.off("transformend.creation");
        dragRect.off("dragend.creation");
      }
      bboxEditable = false;
      const tr: Konva.Transformer = stage?.findOne("#transformer");
      if (tr) tr.nodes([]);
      newShape = { status: "none", shouldReset: true };
      selectedToolStore.set(createPanTool());
    }

    // Brush tool shortcuts
    if (event.key === "b" || event.key === "B") {
      selectedToolStore.set(brushDrawTool);
    }
    if (event.key === "x" || event.key === "X") {
      if (selectedTool?.type === ToolType.Brush) {
        selectedToolStore.set(selectedTool.mode === "draw" ? brushEraseTool : brushDrawTool);
      }
    }
    if (event.key === "[" || event.key === "q" || event.key === "Q") {
      if (selectedTool?.type === ToolType.Brush) {
        brushSettingsStore.update((s) => ({
          ...s,
          brushRadius: Math.max(1, s.brushRadius - 5),
        }));
      }
    }
    if (event.key === "]" || event.key === "e" || event.key === "E") {
      if (selectedTool?.type === ToolType.Brush) {
        brushSettingsStore.update((s) => ({
          ...s,
          brushRadius: Math.min(100, s.brushRadius + 5),
        }));
      }
    }
    if (
      (event.key === "Enter" || event.key === "s" || event.key === "S") &&
      selectedTool?.type === ToolType.Brush
    ) {
      // Save brush mask for all active views
      for (const view_name of Object.keys(imagesPerView)) {
        saveBrushMask(view_name);
      }
    }

    // Smart segmentation: Enter to validate mask and open form
    if (event.key === "Enter" && selectedTool?.isSmart && currentAnn?.output) {
      validateSmartMask();
    }

    // Manual bounding box: Enter to validate and open form
    if (
      event.key === "Enter" &&
      selectedTool?.type === ToolType.Rectangle &&
      !selectedTool.isSmart &&
      newShape.status === "creating" &&
      newShape.type === SaveShapeType.bbox
    ) {
      validateBBox(newShape.viewRef);
    }

    // Polygon: Enter to validate and open form
    if (
      event.key === "Enter" &&
      selectedTool?.type === ToolType.Polygon &&
      newShape.status === "creating" &&
      newShape.type === SaveShapeType.mask &&
      newShape.phase === "editing" &&
      newShape.closedPolygons.length > 0
    ) {
      validatePolygon(newShape.viewRef);
    }

    // Smart segmentation shortcuts
    if (event.key === "w" || event.key === "W") {
      selectedToolStore.set(addSmartPointTool);
    }
    if (event.key === "x" || event.key === "X") {
      if (selectedTool?.type === ToolType.PointSelection) {
        selectedToolStore.set(selectedTool.label === 1 ? removeSmartPointTool : addSmartPointTool);
      }
    }
    if (event.key === "r" || event.key === "R") {
      if (selectedTool?.isSmart) {
        selectedToolStore.set(smartRectangleTool);
      } else {
        selectedToolStore.set(rectangleTool);
      }
    }

    if ((event.key === "Delete" || event.key === "Backspace") && highlighted_point != null) {
      //get view_name of highlighted_point
      const view_name = findViewName(highlighted_point);
      const to_destroy_hl_point = highlighted_point;
      unhighlightInputPoint(highlighted_point, view_name);
      //remove Konva Circle
      to_destroy_hl_point.destroy();

      //if existing construct (points, box, ...)
      const viewLayer = getViewLayer(view_name);
      const inputGroup: Konva.Group = viewLayer.findOne("#input");
      if (inputGroup.children.length > 0) {
        //trigger a currentAnn with existing constructs
        //we do not have view id here, so get it from Konva image "name" field (TODO is it OK for video??)
        const imageKonva = getImageNode(view_name);
        await updateCurrentMask({ id: imageKonva.attrs.name as string, name: view_name });
      } else {
        clearCurrentAnn(view_name, stage, selectedTool);
      }
    }
    if (event.key === "i") {
      console.log("Canvas2D - Infos");
      console.log("masks", masks);
      console.log("bboxes", bboxes);
      console.log("keypoints", keypoints);
      console.log("currentAnn", currentAnn);
      console.log("stage", stage);
      for (const view_name of Object.keys(imagesPerView)) {
        const viewLayer = getViewLayer(view_name);
        const maskGroup: Konva.Group = viewLayer?.findOne(`#masks-${view_name}`);
        const bboxGroup: Konva.Group = viewLayer?.findOne(`#bboxes-${view_name}`);
        const kptGroup: Konva.Group = viewLayer?.findOne(`#keypoints-${view_name}`);
        console.log("view:", view_name);
        console.log("--masks Konva group:", maskGroup);
        console.log("--masks children length:", maskGroup.children?.length);
        console.log("--bboxes Konva group:", bboxGroup);
        console.log("--bboxes children length:", bboxGroup.children?.length);
        console.log("--keypoints Konva group:", kptGroup);
        console.log("--keypoints children length:", kptGroup.children?.length);
      }
    }
  }
</script>

<div
  class={cn("h-full bg-foreground transition-opacity duration-300 delay-100 relative", {
    "opacity-0": !isReady,
  })}
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
                  selectedTool?.type === ToolType.Pan ||
                  selectedTool?.type === ToolType.Delete ||
                  selectedTool?.type === ToolType.Rectangle,
              }}
            >
              {#if (newShape.status === "creating" && newShape.type === SaveShapeType.bbox) || (newShape.status === "saving" && newShape.type === SaveShapeType.bbox)}
                <CreateRectangle
                  zoomFactor={zoomFactor[view_name]}
                  {newShape}
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
                  selectedTool?.type === ToolType.Pan || selectedTool?.type === ToolType.Delete,
              }}
            >
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
                  brushSettings={$brushSettingsStore}
                  existingMaskRle={pendingBrushMask?.viewName === view_name
                    ? pendingBrushMask.rle
                    : null}
                />
              {/if}
              <CreatePolygon {viewRef} {stage} {zoomFactor} bind:newShape />
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
                listening:
                  selectedTool?.type === ToolType.Pan || selectedTool?.type === ToolType.Delete,
              }}
            >
              {#if (newShape.status === "creating" && newShape.type === SaveShapeType.keypoints) || (newShape.status === "saving" && newShape.type === SaveShapeType.keypoints)}
                <CreateKeypoint
                  zoomFactor={zoomFactor[view_name]}
                  bind:newShape
                  {stage}
                  {viewRef}
                />
              {/if}
              {#if !isActivePaintingTool}
                <ShowKeypoints
                  {colorScale}
                  {stage}
                  {viewRef}
                  {keypoints}
                  zoomFactor={zoomFactor[view_name]}
                  bind:newShape
                />
              {/if}
            </Group>
            <Group config={{ id: "currentAnnotation" }} />
          {/if}
        {/each}
        <Group config={{ id: "input" }} />
      </Layer>
    {/each}

    <Layer config={{ name: "tools" }} bind:handle={toolsLayer} />
  </Stage>
</div>
<svelte:window on:keydown={handleKeyDown} />
