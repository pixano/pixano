<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import * as ort from "onnxruntime-web";
  import Konva from "konva";
  import { nanoid } from "nanoid";
  import { afterUpdate, onMount, onDestroy } from "svelte";
  import { Group, Image as KonvaImage, Layer, Stage } from "svelte-konva";
  import { writable, type Writable } from "svelte/store";
  import { WarningModal } from "@pixano/core";

  import { cn } from "@pixano/core/src";
  import type { LabeledClick, Box, InteractiveImageSegmenterOutput } from "@pixano/models";
  import type {
    Mask,
    BBox,
    DatasetItem,
    ItemView,
    SelectionTool,
    LabeledPointTool,
    Shape,
    KeypointsTemplate,
    Vertex,
  } from "@pixano/core";

  import {
    INPUTPOINT_RADIUS,
    INPUTPOINT_STROKEWIDTH,
    // INPUTRECT_STROKEWIDTH,
    // BBOX_STROKEWIDTH,
    // MASK_STROKEWIDTH,
    POINT_SELECTION,
  } from "./lib/constants";
  import { addMask, findOrCreateCurrentMask, clearCurrentAnn } from "./api/boundingBoxesApi";
  import PolygonGroup from "./components/PolygonGroup.svelte";
  import CreatePolygon from "./components/CreatePolygon.svelte";
  import Rectangle from "./components/Rectangle.svelte";
  import CreateRectangle from "./components/CreateRectangle.svelte";
  import CreateKeypoint from "./components/CreateKeypoints.svelte";
  import ShowKeypoints from "./components/ShowKeypoint.svelte";
  import type { Filters } from "@pixano/dataset-item-workspace/src/lib/types/datasetItemWorkspaceTypes";

  // Exports
  export let selectedItemId: DatasetItem["id"];
  export let masks: Mask[];
  export let bboxes: BBox[];
  export let keypoints: KeypointsTemplate[] = [];
  export let selectedKeypointTemplate: KeypointsTemplate | undefined = undefined;
  export let embeddings: Record<string, ort.Tensor> = {};
  export let currentAnn: InteractiveImageSegmenterOutput | null = null;
  export let selectedTool: SelectionTool;
  export let newShape: Shape;
  export let imagesPerView: Record<string, HTMLImageElement[]>;
  export let colorScale: (value: string) => string;
  export let isVideo: boolean = false;
  export let imageSmoothing: boolean = true;

  // Image settings
  export let filters: Writable<Filters> = writable<Filters>();
  export let canvasSize: number = 0;

  let isReady = false;

  let viewEmbeddingModal = false;
  let viewWithoutEmbeddings = "";
  let numberOfBBoxes: number;
  let prevSelectedTool: SelectionTool;
  let zoomFactor: Record<string, number> = {}; // {viewId: zoomFactor}

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
      for (const viewId of Object.keys(imagesPerView)) {
        scaleView(viewId);
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
    width: 1024,
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
    Object.keys(imagesPerView).forEach((viewId) => {
      zoomFactor[viewId] = 1;
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
    Object.keys(imagesPerView).forEach((viewId) => {
      const viewLayer: Konva.Layer = stage.findOne(`#${viewId}`);
      if (viewLayer) viewLayer.add(transformer);
    });

    if (isVideo) return; // Only apply filters to images, because of performance issues

    applyFilters();
  });

  let scaleOnFirstLoad = {};
  let viewReady = {};
  Object.keys(imagesPerView).forEach((viewId) => {
    //we need a first scaleView for image only. If video, the scale is done elsewhere
    scaleOnFirstLoad[viewId] = !isVideo;
    viewReady[viewId] = false;
  });

  const getCurrentImage = (viewId: string) =>
    imagesPerView[viewId][imagesPerView[viewId].length - 1];

  function loadItem() {
    const keys = Object.keys(imagesPerView);
    const totalKeys = keys.length;

    // Calculate new grid size
    gridSize.cols = Math.ceil(Math.sqrt(totalKeys));
    gridSize.rows = Math.ceil(totalKeys / gridSize.cols);

    // Clear annotations in case a previous item was already loaded
    if (currentId) clearAnnotationAndInputs();

    keys.forEach((viewId) => {
      const currentImage = getCurrentImage(viewId);

      currentImage.onload = () => {
        if (scaleOnFirstLoad[viewId]) {
          scaleView(viewId);
          scaleOnFirstLoad[viewId] = false;
        }
        //scaleElements(viewId);
        viewReady[viewId] = true;
        if (Object.values(viewReady).every(Boolean)) {
          isReady = true;
        }
        if (!isVideo) cacheImage();
      };
    });

    currentId = selectedItemId;
  }

  function scaleView(viewId: ItemView["id"]) {
    const viewLayer: Konva.Layer = stage?.findOne(`#${viewId}`);
    if (!viewLayer) {
      console.log("Canvas2D.scaleView - Error: Cannot scale");
      return;
    }
    // Calculate max dims for every image in the grid
    const maxWidth = stage.width() / gridSize.cols;
    const maxHeight = stage.height() / gridSize.rows;

    // Get view index
    const keys = Object.keys(imagesPerView);
    const i = keys.findIndex((view) => view === viewId);

    // Calculate view position in grid
    const grid_pos = {
      x: i % gridSize.cols,
      y: Math.floor(i / gridSize.cols),
    };

    // Fit stage
    const currentImage = getCurrentImage(viewId);
    const scaleByHeight = maxHeight / currentImage.height;
    const scaleByWidth = maxWidth / currentImage.width;
    const scale = Math.min(scaleByWidth, scaleByHeight);

    // Set zoomFactor for view
    zoomFactor[viewId] = scale;
    viewLayer.scale({ x: scale, y: scale });

    // Center view
    const offsetX = (maxWidth - currentImage.width * scale) / 2 + grid_pos.x * maxWidth;
    const offsetY = (maxHeight - currentImage.height * scale) / 2 + grid_pos.y * maxHeight;
    viewLayer.x(offsetX);
    viewLayer.y(offsetY);
  }

  // Unused ... We could remove ?
  // function scaleElements(viewId: ItemView["id"]) {
  //   const viewLayer: Konva.Layer = stage.findOne(`#${viewId}`);
  //   if (!viewLayer) {
  //     console.log("Canvas2D.scaleElements - Error: Cannot scale");
  //     return;
  //   }

  //   const zoom = zoomFactor[viewId];

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

  //   const currentMaskGroup = findOrCreateCurrentMask(viewId, stage);
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

  const EqualizeHistogram = (imageData: ImageData) => {
    const { width, height, data } = imageData;
    const nPixels = width * height;

    // Create histograms for each channel
    const histR: number[] = new Array(256).fill(0) as number[];
    const histG: number[] = new Array(256).fill(0) as number[];
    const histB: number[] = new Array(256).fill(0) as number[];

    // Calculate histograms
    for (let i = 0; i < nPixels * 4; i += 4) {
      histR[data[i]]++;
      histG[data[i + 1]]++;
      histB[data[i + 2]]++;
    }

    // Calculate cumulative distribution function (CDF) for each channel
    const cdfR: number[] = new Array(256).fill(0) as number[];
    const cdfG: number[] = new Array(256).fill(0) as number[];
    const cdfB: number[] = new Array(256).fill(0) as number[];

    cdfR[0] = histR[0];
    cdfG[0] = histG[0];
    cdfB[0] = histB[0];

    for (let i = 1; i < 256; i++) {
      cdfR[i] = cdfR[i - 1] + histR[i];
      cdfG[i] = cdfG[i - 1] + histG[i];
      cdfB[i] = cdfB[i - 1] + histB[i];
    }

    // Normalize the CDF
    const cdfRMin = cdfR.find((value) => value > 0);
    const cdfGMin = cdfG.find((value) => value > 0);
    const cdfBMin = cdfB.find((value) => value > 0);

    for (let i = 0; i < 256; i++) {
      cdfR[i] = ((cdfR[i] - cdfRMin) / (nPixels - cdfRMin)) * 255;
      cdfG[i] = ((cdfG[i] - cdfGMin) / (nPixels - cdfGMin)) * 255;
      cdfB[i] = ((cdfB[i] - cdfBMin) / (nPixels - cdfBMin)) * 255;
    }

    // Apply equalization to the image data
    for (let i = 0; i < nPixels * 4; i += 4) {
      data[i] = Math.round(cdfR[data[i]]);
      data[i + 1] = Math.round(cdfG[data[i + 1]]);
      data[i + 2] = Math.round(cdfB[data[i + 2]]);
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

    let images = stage.find(
      (node: { attrs: { id: string } }): boolean =>
        node.attrs.id && node.attrs.id.startsWith("image-"), // node is of Node type, but the attrs attribute is of any time, which provokes linting errors
    );

    if (!images) return;

    images.forEach((image) => {
      let filtersList = [Konva.Filters.Brighten, Konva.Filters.Contrast, AdjustChannels];
      if ($filters.equalizeHistogram) filtersList.push(EqualizeHistogram);

      image.filters(filtersList);
      image.brightness($filters.brightness);
      image.contrast($filters.contrast);
    });
  };

  function findViewId(shape: Konva.Shape): string {
    let viewId: string;
    shape.getAncestors().forEach((node) => {
      if (node instanceof Konva.Layer) {
        viewId = node.id();
      }
    });
    return viewId;
  }

  // ********** BOUNDING BOXES AND MASKS ********** //

  async function updateCurrentMask(viewId: string) {
    const points = getInputPoints(viewId);
    const box = getInputRect(viewId);
    const input = {
      image: getCurrentImage(viewId),
      embedding: viewId in embeddings ? embeddings[viewId] : null,
      points: points,
      box: box,
    };

    if (selectedTool.postProcessor == null) {
      clearAnnotationAndInputs();
    } else if (embeddings[viewId] == null) {
      viewEmbeddingModal = true;
      viewWithoutEmbeddings = viewId;
      clearAnnotationAndInputs();
    } else {
      const results = await selectedTool.postProcessor.segmentImage(input);
      if (results) {
        newShape = {
          masksImageSVG: results.masksImageSVG,
          rle: results.rle,
          type: "mask",
          viewId,
          itemId: selectedItemId,
          imageWidth: getCurrentImage(viewId).width,
          imageHeight: getCurrentImage(viewId).height,
          status: "saving",
        };

        const currentMaskGroup = findOrCreateCurrentMask(viewId, stage);
        const viewLayer: Konva.Layer = stage.findOne(`#${viewId}`);
        const image: Konva.Image = viewLayer.findOne(`#image-${viewId}`);

        // always clean existing masks before adding a new currentAnn
        currentMaskGroup.removeChildren();

        currentAnn = {
          id: nanoid(10),
          viewId: viewId,
          label: "",
          catId: -1,
          output: results,
          input_points: points,
          input_box: box,
          validated: false,
        };
        const currentMask = <Mask>{
          id: currentAnn.id,
          viewId: viewId,
          svg: currentAnn.output.masksImageSVG,
          rle: currentAnn.output.rle,
          catId: currentAnn.catId,
          visible: true,
          opacity: 1.0,
        };

        addMask(currentMask, "#008000", currentMaskGroup, image, viewId, stage, zoomFactor);
      }
    }
  }

  // ********** CURRENT ANNOTATION ********** //

  function validateCurrentAnn() {
    if (currentAnn.validated) {
      const currentMaskGroup = findOrCreateCurrentMask(currentAnn.viewId, stage);
      if (currentMaskGroup) currentMaskGroup.destroyChildren();
      if (highlighted_point) unhighlightInputPoint(highlighted_point);
      clearInputs(currentAnn.viewId);
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
      case "POINT_SELECTION":
        displayInputPointTool(selectedTool);
        break;
      case "RECTANGLE":
        displayInputRectTool(selectedTool);
        // Enable box creation or change cursor style
        break;
      case "KEY_POINT":
        // Enable key point creation or change cursor style
        break;
      case "DELETE":
        clearAnnotationAndInputs();
        displayInputDeleteTool(selectedTool);
        break;
      case "PAN":
        displayPanTool(selectedTool);
        // Enable box creation or change cursor style
        break;
      case "CLASSIFICATION":
        displayClassificationTool(selectedTool);
        break;

      default:
        // Reset or disable any specific behavior
        break;
    }
  }

  function clearInputs(viewId: string) {
    const viewLayer: Konva.Layer = stage?.findOne(`#${viewId}`);
    if (viewLayer) {
      const inputGroup: Konva.Group = viewLayer.findOne("#input");
      inputGroup.destroyChildren();
    }
  }

  // ********** POLYGON TOOL ********** //

  function drawPolygonPoints(viewId: string) {
    if (newShape?.status === "saving") return;
    const viewLayer: Konva.Layer = stage.findOne(`#${viewId}`);
    const cursorPositionOnImage = viewLayer.getRelativePointerPosition();
    const x = Math.round(cursorPositionOnImage.x);
    const y = Math.round(cursorPositionOnImage.y);

    const oldPoints =
      newShape.status === "creating" && newShape.type === "mask" ? newShape.points : [];
    newShape = {
      status: "creating",
      type: "mask",
      points: [...oldPoints, { x, y, id: oldPoints.length || 0 }],
      viewId,
    };
  }

  // ********** KEY_POINT TOOL ********** //

  function dragInputKeyPointRectMove(viewId: string) {
    if (selectedTool?.type === "KEY_POINT" && newShape.status !== "saving") {
      const viewLayer: Konva.Layer = stage.findOne(`#${viewId}`);

      const pos = viewLayer.getRelativePointerPosition();
      const x = newShape.status === "creating" && newShape.type === "keypoint" ? newShape.x : pos.x;
      const y = newShape.status === "creating" && newShape.type === "keypoint" ? newShape.y : pos.y;
      const width = pos.x - x;
      const height = pos.y - y;
      newShape = {
        status: "creating",
        type: "keypoint",
        x,
        y,
        width,
        height,
        viewId,
        keypoints: selectedKeypointTemplate,
      };
    }
  }

  function dragKeyPointInputRectEnd(viewId: string) {
    if (selectedTool?.type == "KEY_POINT") {
      const viewLayer: Konva.Layer = stage.findOne(`#${viewId}`);
      const rect: Konva.Rect = stage.findOne("#move-keyPoints-group");
      if (rect && newShape.status === "creating" && newShape.type === "keypoint") {
        const vertices = newShape.keypoints.vertices.map((vertex) => {
          if (newShape.status === "creating" && newShape.type === "keypoint")
            return {
              ...vertex,
              x: newShape.x + vertex.x * newShape.width,
              y: newShape.y + vertex.y * newShape.height,
            } as Required<Vertex>;
        });
        newShape = {
          status: "saving",
          type: "keypoint",
          viewId,
          itemId: selectedItemId,
          imageWidth: getCurrentImage(viewId).width,
          imageHeight: getCurrentImage(viewId).height,
          keypoints: { ...newShape.keypoints, vertices },
        };
        rect.destroy();
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

  function findOrCreateInputPointPointer(id: string, viewId: string = null): Konva.Circle {
    let pointer: Konva.Circle = stage.findOne(`#${id}`);
    if (!pointer) {
      let zoomF = 1.0; // in some cases we aren't in a view, so we use default scaling
      if (viewId) zoomF = zoomFactor[viewId];
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

  function getInputPoints(viewId: string): Array<LabeledClick> {
    //get points as Array<LabeledClick>
    const points: Array<LabeledClick> = [];
    const viewLayer: Konva.Layer = stage.findOne(`#${viewId}`);
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

  function dragInputPointMove(drag_point: Konva.Circle, viewId: string) {
    stage.container().style.cursor = "grabbing";

    const viewLayer: Konva.Layer = stage.findOne(`#${viewId}`);
    const image: Konva.Image = viewLayer.findOne(`#image-${viewId}`);
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

    // new currentAnn on new location
    clearTimeout(timerId); // reinit timer on each move move
    // eslint-disable-next-line @typescript-eslint/no-misused-promises
    timerId = setTimeout(() => updateCurrentMask(viewId), 50); // delay before predict to spare CPU
  }

  function highlightInputPoint(hl_point: Konva.Circle, viewId: string) {
    const pointer = findOrCreateInputPointPointer(selectedTool.type, viewId);
    pointer.hide();
    hl_point.radius((1.5 * INPUTPOINT_RADIUS) / zoomFactor[viewId]);
    highlighted_point = hl_point;
    stage.container().style.cursor = "grab";
  }

  function unhighlightInputPoint(hl_point: Konva.Circle, viewId: string = null) {
    const pointer = findOrCreateInputPointPointer(selectedTool.type, viewId);
    pointer.show();
    if (!viewId) {
      viewId = findViewId(hl_point);
    }
    hl_point.radius(INPUTPOINT_RADIUS / zoomFactor[viewId]);
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

  function getInputRect(viewId: string): Box {
    //get box as Box
    let box: Box = null;
    const viewLayer: Konva.Layer = stage.findOne(`#${viewId}`);
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

  function dragInputRectMove(viewId: string) {
    if (selectedTool?.type === "RECTANGLE") {
      const viewLayer: Konva.Layer = stage.findOne(`#${viewId}`);

      const pos = viewLayer.getRelativePointerPosition();
      const x =
        newShape.status === "creating" && newShape.type === "rectangle" ? newShape.x : pos.x;
      const y =
        newShape.status === "creating" && newShape.type === "rectangle" ? newShape.y : pos.y;
      newShape = {
        status: "creating",
        type: "rectangle",
        x,
        y,
        width: pos.x - x,
        height: pos.y - y,
        viewId,
      };
    }
  }

  async function dragInputRectEnd(viewId: string) {
    if (selectedTool?.type == "RECTANGLE") {
      const viewLayer: Konva.Layer = stage.findOne(`#${viewId}`);
      const rect: Konva.Rect = stage.findOne("#drag-rect");
      if (rect) {
        const { width, height } = rect.size();
        if (width == 0 || height == 0) {
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
              type: "rectangle",
              viewId,
              itemId: selectedItemId,
              imageWidth: getCurrentImage(viewId).width,
              imageHeight: getCurrentImage(viewId).height,
            };
          }
          selectedTool.isSmart && (await updateCurrentMask(viewId));
        }
        viewLayer.off("pointermove");
        viewLayer.off("pointerup");
      }
      if (selectedTool.isSmart) {
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
    for (const viewId of Object.keys(imagesPerView)) {
      clearInputs(viewId);
      clearCurrentAnn(viewId, stage, selectedTool);
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
    if (selectedTool?.type === "POINT_SELECTION") {
      updateInputPointStage(position);
    }

    if (selectedTool?.type === "RECTANGLE") {
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

  function handleDragEndOnView(viewId: string) {
    const viewLayer: Konva.Layer = stage.findOne(`#${viewId}`);
    viewLayer.draggable(false);
    viewLayer.off("dragend dragmove");
  }

  function handlePointerUpOnImage(viewId: string) {
    const viewLayer: Konva.Layer = stage.findOne(`#${viewId}`);
    viewLayer.draggable(false);
    viewLayer.off("dragend dragmove");
    if (selectedTool?.type === "POLYGON") {
      drawPolygonPoints(viewId);
    }

    if (highlighted_point) {
      //hack to unhiglight when we drag while predicting...
      //try to determine if we are still on highlighted point
      //Note: could be better, but usually it will work
      const pos = viewLayer.getRelativePointerPosition();
      const hl_pos = highlighted_point.position();
      if (pos.x !== hl_pos.x || pos.y !== hl_pos.y)
        unhighlightInputPoint(highlighted_point, viewId);
    }
  }

  function handleDoubleClickOnImage(viewId: string) {
    // put double-clickd view on top of views
    const viewLayer: Konva.Layer = stage.findOne(`#${viewId}`);
    viewLayer.moveToTop();
    //keeps tools on top
    toolsLayer.moveToTop();
  }

  async function handleClickOnImage(event: PointerEvent, viewId: string) {
    const viewLayer: Konva.Layer = stage.findOne(`#${viewId}`);

    if (newShape.status === "none" || newShape.status == "editing") {
      newShape = {
        status: "editing",
        viewId,
        type: "none",
        shapeId: null,
        highlighted: "all",
      };
    }
    // Perform tool action if any active tool
    // For convenience: bypass tool on mouse middle-button click
    if (selectedTool?.type == "PAN" || event.button == 1) {
      viewLayer.draggable(true);
      viewLayer.on("dragmove", handleMouseMoveStage);
      viewLayer.on("dragend", () => handleDragEndOnView(viewId));
    } else if (selectedTool?.type == "POINT_SELECTION") {
      const clickOnViewPos = viewLayer.getRelativePointerPosition();

      //add Konva Point
      const input_point = new Konva.Circle({
        name: `${selectedTool.label}`,
        x: clickOnViewPos.x,
        y: clickOnViewPos.y,
        radius: INPUTPOINT_RADIUS / zoomFactor[viewId],
        stroke: "white",
        fill: selectedTool.label === 1 ? "green" : "red",
        strokeWidth: INPUTPOINT_STROKEWIDTH / zoomFactor[viewId],
        visible: true,
        listening: true,
        opacity: 0.75,
        draggable: true,
      });
      input_point.on("pointerenter", (event) =>
        highlightInputPoint(event.target as Konva.Circle, viewId),
      );
      input_point.on("pointerout", (event) =>
        unhighlightInputPoint(event.target as Konva.Circle, viewId),
      );
      input_point.on(
        "dragmove",
        (event) => void dragInputPointMove(event.target as Konva.Circle, viewId),
      );
      input_point.on("dragend", () => dragInputPointEnd());
      const inputGroup: Konva.Group = viewLayer.findOne("#input");
      inputGroup.add(input_point);
      highlightInputPoint(input_point, viewId);
      await updateCurrentMask(viewId);
    } else if (selectedTool?.type == "RECTANGLE") {
      viewLayer.on("pointermove", () => dragInputRectMove(viewId));
      viewLayer.on("pointerup", () => void dragInputRectEnd(viewId));
    } else if (selectedTool?.type === "KEY_POINT") {
      viewLayer.on("pointermove", () => dragInputKeyPointRectMove(viewId));
      viewLayer.on("pointerup", () => void dragKeyPointInputRectEnd(viewId));
    }
  }

  function zoom(stage: Konva.Stage, direction: number, viewId: string): number {
    // Defines zoom speed
    const zoomScale = 1.05;

    const viewLayer: Konva.Layer = stage.findOne(`#${viewId}`);

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

  function handleWheelOnImage(event: WheelEvent, viewId: ItemView["id"]) {
    // Prevent default scrolling
    event.preventDefault();

    // Get zoom direction
    let direction = event.deltaY < 0 ? 1 : -1;

    // Revert direction for trackpad
    if (event.ctrlKey) direction = -direction;

    // Zoom
    zoomFactor[viewId] = zoom(stage, direction, viewId);
    //scaleElements(viewId);

    // Keep highlighted point scaling
    if (highlighted_point) highlightInputPoint(highlighted_point, viewId);
  }

  // ********** KEY EVENTS ********** //

  async function handleKeyDown(event: KeyboardEvent) {
    if (event.key == "Delete" && highlighted_point != null) {
      //get viewId of highlighted_point
      const viewId = findViewId(highlighted_point);
      const to_destroy_hl_point = highlighted_point;
      unhighlightInputPoint(highlighted_point, viewId);
      //remove Konva Circle
      to_destroy_hl_point.destroy();

      //if existing construct (points, box, ...)
      const viewLayer: Konva.Layer = stage.findOne(`#${viewId}`);
      const inputGroup: Konva.Group = viewLayer.findOne("#input");
      if (inputGroup.children.length > 0) {
        //trigger a currentAnn with existing constructs
        await updateCurrentMask(viewId);
      } else {
        clearCurrentAnn(viewId, stage, selectedTool);
      }
    }
    if (event.key == "i") {
      console.log("Canvas2D - Infos");
      console.log("masks", masks);
      console.log("bboxes", bboxes);
      console.log("currentAnn", currentAnn);
      console.log("stage", stage);
      for (const viewId of Object.keys(imagesPerView)) {
        const viewLayer: Konva.Layer = stage.findOne(`#${viewId}`);
        const maskGroup: Konva.Group = viewLayer.findOne("#masks");
        const bboxGroup: Konva.Group = viewLayer.findOne("#bboxes");
        console.log("view:", viewId);
        console.log("--masks Konva group:", maskGroup);
        console.log("--masks children length:", maskGroup.children?.length);
        console.log("--bboxes Konva group:", bboxGroup);
        console.log("--bboxes children length:", bboxGroup.children?.length);
      }
    }
  }
</script>

<div
  class={cn("h-full bg-slate-800 transition-opacity duration-300 delay-100 relative", {
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
    {#each Object.entries(imagesPerView) as [viewId, images]}
      <Layer
        config={{ id: viewId, imageSmoothingEnabled: imageSmoothing }}
        on:wheel={(event) => handleWheelOnImage(event.detail.evt, viewId)}
      >
        {#each images as image}
          <KonvaImage
            config={{
              image,
              id: `image-${viewId}`,
            }}
            on:pointerdown={(event) => handleClickOnImage(event.detail.evt, viewId)}
            on:pointerup={() => handlePointerUpOnImage(viewId)}
            on:dblclick={() => handleDoubleClickOnImage(viewId)}
          />
        {/each}
        <Group config={{ id: "currentAnnotation" }} />
        <Group config={{ id: "input" }} />
        <Group config={{ id: "bboxes" }}>
          {#if (newShape.status === "creating" && newShape.type === "rectangle") || (newShape.status === "saving" && newShape.type === "rectangle")}
            <CreateRectangle zoomFactor={zoomFactor[viewId]} {newShape} {stage} {viewId} />
          {/if}
          {#each bboxes as bbox}
            {#if bbox.viewId === viewId}
              <Rectangle
                {bbox}
                {colorScale}
                zoomFactor={zoomFactor[viewId]}
                {stage}
                {viewId}
                bind:newShape
                {selectedTool}
              />
            {/if}
          {/each}
        </Group>
        <Group config={{ id: "masks" }}>
          <CreatePolygon
            {viewId}
            {stage}
            currentImage={getCurrentImage(viewId)}
            {zoomFactor}
            {selectedItemId}
            bind:newShape
          />
          {#each masks as mask (mask.id)}
            {#if mask.viewId === viewId}
              <PolygonGroup
                {viewId}
                bind:newShape
                {stage}
                currentImage={getCurrentImage(viewId)}
                {zoomFactor}
                {mask}
                color={colorScale(mask.id)}
                {selectedTool}
              />
            {/if}
          {/each}
        </Group>
        <Group config={{ id: "keypoints" }}>
          {#if (newShape.status === "creating" && newShape.type === "keypoint") || (newShape.status === "saving" && newShape.type === "keypoint")}
            <CreateKeypoint zoomFactor={zoomFactor[viewId]} bind:newShape {stage} {viewId} />
          {/if}
          <ShowKeypoints
            {colorScale}
            {stage}
            {viewId}
            {keypoints}
            zoomFactor={zoomFactor[viewId]}
            bind:newShape
          />
        </Group>
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
