<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import Konva from "konva";
  import { nanoid } from "nanoid";
  import * as ort from "onnxruntime-web";
  import { afterUpdate, onDestroy, onMount } from "svelte";
  import { Group, Image as KonvaImage, Layer, Stage } from "svelte-konva";
  import { writable, type Writable } from "svelte/store";

  import {
    Annotation,
    BBox,
    Mask,
    SaveShapeType,
    WarningModal,
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
  import type { Filters } from "@pixano/dataset-item-workspace/src/lib/types/datasetItemWorkspaceTypes";
  import type { Box, InteractiveImageSegmenterOutput, LabeledClick } from "@pixano/models";
  import { convertSegmentsToSVG, generatePolygonSegments } from "@pixano/models/src/mask_utils";

  import { isLocalSegmentationModel } from "../../../apps/pixano/src/lib/stores/datasetStores";
  import { addMask, clearCurrentAnn, findOrCreateCurrentMask } from "./api/boundingBoxesApi";
  import CreateKeypoint from "./components/CreateKeypoints.svelte";
  import CreatePolygon from "./components/CreatePolygon.svelte";
  import CreateRectangle from "./components/CreateRectangle.svelte";
  import PolygonGroup from "./components/PolygonGroup.svelte";
  import Rectangle from "./components/Rectangle.svelte";
  import ShowKeypoints from "./components/ShowKeypoint.svelte";
  import {
    INPUTPOINT_RADIUS,
    INPUTPOINT_STROKEWIDTH,
    // INPUTRECT_STROKEWIDTH,
    // BBOX_STROKEWIDTH,
    // MASK_STROKEWIDTH,
    POINT_SELECTION,
  } from "./lib/constants";
  import { equalizeHistogram } from "./lib/utils/equalizeHistogram";
  import { ToolType } from "./tools";

  // Exports
  export let selectedItemId: string;
  export let masks: Mask[];
  export let bboxes: BBox[];
  export let keypoints: KeypointsTemplate[] = [];
  export let selectedKeypointTemplate: KeypointsTemplate | undefined = undefined;
  export let embeddings: Record<string, ort.Tensor> = {};
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

  let viewEmbeddingModal = false;
  let viewWithoutEmbeddings = "";
  let numberOfBBoxes: number;
  let prevSelectedTool: SelectionTool;
  let zoomFactor: Record<string, number> = {}; // {view_name: zoomFactor}

  let lastInputViewRef: Reference;

  $: {
    if (
      !prevSelectedTool?.isSmart ||
      !selectedTool?.isSmart ||
      (newShape.status === "none" && newShape.shouldReset)
    ) {
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
  let highlighted_point: Konva.Circle = null;
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
        stage.batchDraw();
      }
    }
  });

  // ********** INIT ********** //

  onMount(() => {
    Object.keys(imagesPerView).forEach((view_name) => {
      zoomFactor[view_name] = 1;
    });
    loadItem();
    // Fire stage events observers
    resizeObserver.observe(stageContainer);
  });

  onDestroy(() => {
    clearAnnotationAndInputs();
  });

  afterUpdate(() => {
    if (currentId !== selectedItemId) loadItem();

    if (selectedTool) {
      handleChangeTool();
    } else {
      // reset
      stage.container().style.cursor = "default";
    }
    if (currentAnn && currentAnn.validated) {
      validateCurrentAnn();
    }

    // Add transformer to view layers
    Object.keys(imagesPerView).forEach((view_name) => {
      const viewLayer: Konva.Layer = stage.findOne(`#${view_name}`);
      if (viewLayer) viewLayer.add(transformer);
    });

    if (isVideo) return; // Only apply filters to images, because of performance issues

    applyFilters();
  });

  let scaleOnFirstLoad = {};
  let viewReady = {};
  Object.keys(imagesPerView).forEach((view_name) => {
    //we need a first scaleView for image only. If video, the scale is done elsewhere
    scaleOnFirstLoad[view_name] = !isVideo;
    viewReady[view_name] = false;
  });

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

    keys.forEach((view_name) => {
      const currentImage = getCurrentImage(view_name);

      currentImage.onload = () => {
        if (scaleOnFirstLoad[view_name]) {
          scaleView(view_name);
          scaleOnFirstLoad[view_name] = false;
        }
        //scaleElements(view_name);
        viewReady[view_name] = true;
        if (Object.values(viewReady).every(Boolean)) {
          isReady = true;
        }
        if (!isVideo) cacheImage();
      };
    });

    currentId = selectedItemId;
  }

  function scaleView(view_name: string) {
    const viewLayer: Konva.Layer = stage?.findOne(`#${view_name}`);
    if (!viewLayer) {
      console.log("Canvas2D.scaleView - Error: Cannot scale");
      return;
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

    let images = stage.find(
      (node: { attrs: { id: string } }): boolean =>
        node.attrs.id && node.attrs.id.startsWith("image-"), // node is of Node type, but the attrs attribute is of any time, which provokes linting errors
    );

    if (!images) return;

    images.forEach((image) => {
      if (image.width() === 0 || image.height() === 0) return;
      image.cache();
    });
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

    let images = stage.find(
      (node: { attrs: { id: string } }): boolean =>
        node.attrs.id && node.attrs.id.startsWith("image-"), // node is of Node type, but the attrs attribute is of any type, which provokes linting errors
    );

    if (!images) return;

    images.forEach((image) => {
      let filtersList = [Konva.Filters.Brighten, Konva.Filters.Contrast, AdjustChannels];
      if ($filters.equalizeHistogram) filtersList.push(equalizeHistogram);

      image.filters(filtersList);
      image.brightness($filters.brightness);
      image.contrast($filters.contrast);
    });
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
  $: if (
    isVideo &&
    !$isLocalSegmentationModel &&
    $pixanoInferenceTracking.mustValidate &&
    $pixanoInferenceTracking.validated
  ) {
    if (lastInputViewRef != undefined) {
      void updateCurrentMask(lastInputViewRef);
    }
  }

  async function updateCurrentMask(viewRef: Reference) {
    let results: SegmentationResult = null;

    const points = getInputPoints(viewRef.name);
    const box = getInputRect(viewRef.name);
    const currentImage = getCurrentImage(viewRef.name);

    if ($isLocalSegmentationModel) {
      if (selectedTool.postProcessor == null) {
        clearAnnotationAndInputs();
      } else if (embeddings[viewRef.id] == null) {
        viewEmbeddingModal = true;
        viewWithoutEmbeddings = viewRef.name;
        clearAnnotationAndInputs();
      } else {
        const input = {
          image: currentImage,
          embedding: viewRef.id in embeddings ? embeddings[viewRef.id] : null,
          points: points,
          box: box,
        };
        results = await selectedTool.postProcessor.segmentImage(input);
      }
    } else {
      // infer
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
    }

    if (results) {
      newShape = {
        masksImageSVG: results.masksImageSVG,
        rle: results.rle,
        type: SaveShapeType.mask,
        viewRef,
        itemId: selectedItemId,
        imageWidth: currentImage.width,
        imageHeight: currentImage.height,
        status: "saving",
      };
      const currentMaskGroup = findOrCreateCurrentMask(viewRef.name, stage);
      const viewLayer: Konva.Layer = stage.findOne(`#${viewRef.name}`);
      const image: Konva.Image = viewLayer.findOne(`#image-${viewRef.name}`);

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
        "#008000",
        currentMaskGroup,
        image,
        viewRef.name,
        stage,
        zoomFactor,
      );
    }
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
        break;
      case ToolType.Rectangle:
        displayInputRectTool(selectedTool);
        // Enable box creation or change cursor style
        break;
      case ToolType.Keypoint:
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

      default:
        // Reset or disable any specific behavior
        break;
    }
  }

  function clearInputs(view_name: string) {
    const viewLayer: Konva.Layer = stage?.findOne(`#${view_name}`);
    if (viewLayer) {
      const inputGroup: Konva.Group = viewLayer.findOne("#input");
      inputGroup.destroyChildren();
    }
  }

  // ********** POLYGON TOOL ********** //

  function drawPolygonPoints(viewRef: Reference) {
    if (newShape?.status === "saving") return;
    const viewLayer: Konva.Layer = stage.findOne(`#${viewRef.name}`);
    const cursorPositionOnImage = viewLayer.getRelativePointerPosition();
    const x = Math.round(cursorPositionOnImage.x);
    const y = Math.round(cursorPositionOnImage.y);

    const oldPoints =
      newShape.status === "creating" && newShape.type === SaveShapeType.mask ? newShape.points : [];
    newShape = {
      status: "creating",
      type: SaveShapeType.mask,
      points: [...oldPoints, { x, y, id: oldPoints.length || 0 }],
      viewRef,
    };
  }

  // ********** KEY_POINT TOOL ********** //

  function dragInputKeyPointRectMove(viewRef: Reference) {
    if (selectedTool?.type === ToolType.Keypoint && newShape.status !== "saving") {
      const viewLayer: Konva.Layer = stage.findOne(`#${viewRef.name}`);

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
      const viewLayer: Konva.Layer = stage.findOne(`#${viewRef.name}`);
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

  // ********** INPUT POINTS TOOL ********** //

  function displayInputPointTool(tool: LabeledPointTool) {
    if (toolsLayer) {
      //clean other tools
      //TODO: etre générique sur l'ensemble des outils != Point
      const crossline = toolsLayer.findOne("#crossline");
      if (crossline) crossline.destroy();

      const pointer = findOrCreateInputPointPointer(tool.type);
      const pointerColor = tool.label === 1 ? "green" : "red";
      pointer.stroke(pointerColor);
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
    pointer.x(mousePos.x + 1);
    pointer.y(mousePos.y + 1);
  }

  function findOrCreateInputPointPointer(id: string, view_name: string = null): Konva.Circle {
    let pointer: Konva.Circle = stage.findOne(`#${id}`);
    if (!pointer) {
      let zoomF = 1.0; // in some cases we aren't in a view, so we use default scaling
      if (view_name) zoomF = zoomFactor[view_name];
      pointer = new Konva.Circle({
        id,
        x: 0,
        y: 0,
        radius: INPUTPOINT_RADIUS / zoomF,
        fill: "white",
        strokeWidth: INPUTPOINT_STROKEWIDTH / zoomF,
        visible: false,
        listening: false,
        opacity: 0.5,
      });
      toolsLayer.add(pointer);
    }
    return pointer;
  }

  function getInputPoints(view_name: string): Array<LabeledClick> {
    //get points as Array<LabeledClick>
    const points: Array<LabeledClick> = [];
    const viewLayer: Konva.Layer = stage.findOne(`#${view_name}`);
    const inputGroup: Konva.Group = viewLayer.findOne("#input");
    for (const pt of inputGroup.children) {
      if (pt instanceof Konva.Circle) {
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
        if (node instanceof Konva.Circle) {
          node.listening(toggle);
        }
      }
    }
  }

  function dragInputPointEnd() {
    stage.container().style.cursor = "grab";
  }

  function dragInputPointMove(drag_point: Konva.Circle, viewRef: Reference) {
    stage.container().style.cursor = "grabbing";

    const viewLayer: Konva.Layer = stage.findOne(`#${viewRef.name}`);
    const image: Konva.Image = viewLayer.findOne(`#image-${viewRef.name}`);
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

  function highlightInputPoint(hl_point: Konva.Circle, view_name: string) {
    const pointer = findOrCreateInputPointPointer(selectedTool.type, view_name);
    pointer.hide();
    hl_point.radius((1.5 * INPUTPOINT_RADIUS) / zoomFactor[view_name]);
    highlighted_point = hl_point;
    stage.container().style.cursor = "grab";
  }

  function unhighlightInputPoint(hl_point: Konva.Circle, view_name: string = null) {
    const pointer = findOrCreateInputPointPointer(selectedTool.type, view_name);
    pointer.show();
    if (!view_name) {
      view_name = findViewName(hl_point);
    }
    hl_point.radius(INPUTPOINT_RADIUS / zoomFactor[view_name]);
    highlighted_point = null;
    stage.container().style.cursor = selectedTool.cursor;
    stage.batchDraw();
  }

  // ********** INPUT RECTANGLE TOOL ********** //

  function displayInputRectTool(tool: SelectionTool) {
    if (toolsLayer) {
      //clean other tools
      // TODO: être générique sur l'ensemble des outils != Rectangle
      const pointer = stage.findOne(`#${POINT_SELECTION}`);
      if (pointer) pointer.destroy();
      if (!highlighted_point) {
        stage.container().style.cursor = tool.cursor;
      }
      // activate drag on input points
      toggleInputPointDrag(true);
    }
  }

  function updateInputRectState(mousePos: Konva.Vector2d) {
    const scale = stage.scaleX();
    const lineScale = Math.max(1, 1 / scale);

    const [xLimit, yLimit] = findOrCreateInputRectPointer();
    const stageHeight = stage.height();
    xLimit.scaleY(lineScale);
    xLimit.points([mousePos.x, 0, mousePos.x, stageHeight]);
    const stageWidth = stage.width();
    yLimit.scaleX(lineScale);
    yLimit.points([0, mousePos.y, stageWidth, mousePos.y]);
  }

  function findOrCreateInputRectPointer(): Konva.Line[] {
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
    const viewLayer: Konva.Layer = stage.findOne(`#${view_name}`);
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
      const viewLayer: Konva.Layer = stage.findOne(`#${viewRef.name}`);

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
      const viewLayer: Konva.Layer = stage.findOne(`#${viewRef.name}`);
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
    const pointer: Konva.Circle = stage.findOne(`#${POINT_SELECTION}`);
    if (pointer) pointer.destroy();
    const crossline = toolsLayer?.findOne("#crossline");
    if (crossline) crossline.destroy();
    currentAnn = null;
  }

  // ********** MOUSE EVENTS ********** //

  function handleMouseMoveStage() {
    const position = stage.getRelativePointerPosition();

    // Update tools states
    if (selectedTool?.type === ToolType.PointSelection) {
      updateInputPointStage(position);
    }

    if (selectedTool?.type === ToolType.Rectangle) {
      updateInputRectState(position);
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
  }

  function handleDragEndOnView(view_name: string) {
    const viewLayer: Konva.Layer = stage.findOne(`#${view_name}`);
    viewLayer.draggable(false);
    viewLayer.off("dragend dragmove");
  }

  function handlePointerUpOnImage(viewRef: Reference) {
    const viewLayer: Konva.Layer = stage.findOne(`#${viewRef.name}`);
    viewLayer.draggable(false);
    viewLayer.off("dragend dragmove");
    if (selectedTool?.type === ToolType.Polygon) {
      drawPolygonPoints(viewRef);
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
    const viewLayer: Konva.Layer = stage.findOne(`#${view_name}`);
    viewLayer.moveToTop();
    //keeps tools on top
    toolsLayer.moveToTop();
  }

  async function handleClickOnImage(event: PointerEvent, viewRef: Reference) {
    const viewLayer: Konva.Layer = stage.findOne(`#${viewRef.name}`);

    if (newShape.status === "none" || newShape.status === "editing") {
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
      const input_point = new Konva.Circle({
        name: `${selectedTool.label}`,
        x: clickOnViewPos.x,
        y: clickOnViewPos.y,
        radius: INPUTPOINT_RADIUS / zoomFactor[viewRef.name],
        stroke: "white",
        fill: selectedTool.label === 1 ? "green" : "red",
        strokeWidth: INPUTPOINT_STROKEWIDTH / zoomFactor[viewRef.name],
        visible: true,
        listening: true,
        opacity: 0.75,
        draggable: true,
      });
      input_point.on("pointerenter", (event) =>
        highlightInputPoint(event.target as Konva.Circle, viewRef.name),
      );
      input_point.on("pointerout", (event) =>
        unhighlightInputPoint(event.target as Konva.Circle, viewRef.name),
      );
      input_point.on(
        "dragmove",
        (event) => void dragInputPointMove(event.target as Konva.Circle, viewRef),
      );
      input_point.on("dragend", () => dragInputPointEnd());
      const inputGroup: Konva.Group = viewLayer.findOne("#input");
      inputGroup.add(input_point);
      inputGroup.moveToTop(); //ensure input points stay over other groups
      highlightInputPoint(input_point, viewRef.name);
      lastInputViewRef = viewRef;
      await updateCurrentMask(viewRef);
    } else if (selectedTool?.type === ToolType.Rectangle) {
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

    const viewLayer: Konva.Layer = stage.findOne(`#${view_name}`);

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

    if (event.key === "Delete" && highlighted_point != null) {
      //get view_name of highlighted_point
      const view_name = findViewName(highlighted_point);
      const to_destroy_hl_point = highlighted_point;
      unhighlightInputPoint(highlighted_point, view_name);
      //remove Konva Circle
      to_destroy_hl_point.destroy();

      //if existing construct (points, box, ...)
      const viewLayer: Konva.Layer = stage.findOne(`#${view_name}`);
      const inputGroup: Konva.Group = viewLayer.findOne("#input");
      if (inputGroup.children.length > 0) {
        //trigger a currentAnn with existing constructs
        //we do not have view id here, so get it from Konva image "name" field (TODO is it OK for video??)
        const imageKonva: Konva.Image = viewLayer.findOne(`#image-${view_name}`);
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
        const viewLayer: Konva.Layer = stage.findOne(`#${view_name}`);
        const maskGroup: Konva.Group = viewLayer.findOne(`#masks-${view_name}`);
        const bboxGroup: Konva.Group = viewLayer.findOne(`#bboxes-${view_name}`);
        const kptGroup: Konva.Group = viewLayer.findOne(`#keypoints-${view_name}`);
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
            <Group config={{ id: `bboxes-${view_name}` }}>
              {#if (newShape.status === "creating" && newShape.type === SaveShapeType.bbox) || (newShape.status === "saving" && newShape.type === SaveShapeType.bbox)}
                <CreateRectangle zoomFactor={zoomFactor[view_name]} {newShape} {stage} {viewRef} />
              {/if}
              {#each bboxes as bbox}
                {#if bbox.data.view_ref.name === view_name}
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
            <Group config={{ id: `masks-${view_name}` }}>
              <CreatePolygon
                {viewRef}
                {stage}
                currentImage={getCurrentImage(view_name)}
                {zoomFactor}
                {selectedItemId}
                bind:newShape
              />
              {#each masks as mask (mask.id)}
                {#if mask.data.view_ref.name === view_name}
                  <PolygonGroup
                    {viewRef}
                    bind:newShape
                    {stage}
                    currentImage={getCurrentImage(view_name)}
                    {zoomFactor}
                    {mask}
                    color={colorScale(
                      mask.ui.top_entities && mask.ui.top_entities.length > 0
                        ? mask.ui.top_entities[0].id
                        : mask.data.entity_ref.id,
                    )}
                    {selectedTool}
                  />
                {/if}
              {/each}
            </Group>
            <Group config={{ id: `keypoints-${view_name}` }}>
              {#if (newShape.status === "creating" && newShape.type === SaveShapeType.keypoints) || (newShape.status === "saving" && newShape.type === SaveShapeType.keypoints)}
                <CreateKeypoint
                  zoomFactor={zoomFactor[view_name]}
                  bind:newShape
                  {stage}
                  {viewRef}
                />
              {/if}
              <ShowKeypoints
                {colorScale}
                {stage}
                {viewRef}
                {keypoints}
                zoomFactor={zoomFactor[view_name]}
                bind:newShape
              />
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
{#if viewEmbeddingModal}
  <WarningModal
    message="No embeddings found for view '{viewWithoutEmbeddings}'."
    details="The embeddings may not have finished loading yet. Please try again."
    on:confirm={() => (viewEmbeddingModal = false)}
  />
{/if}
<svelte:window on:keydown={handleKeyDown} />
