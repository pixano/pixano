<script lang="ts">
  /**
   * @copyright CEA
   * @author CEA
   * @license CECILL
   *
   * This software is a collaborative computer program whose purpose is to
   * generate and explore labeled data for computer vision applications.
   * This software is governed by the CeCILL-C license under French law and
   * abiding by the rules of distribution of free software. You can use,
   * modify and/ or redistribute the software under the terms of the CeCILL-C
   * license as circulated by CEA, CNRS and INRIA at the following URL
   *
   * http://www.cecill.info
   */

  // Imports
  import * as ort from "onnxruntime-web";
  import Konva from "konva";
  import { nanoid } from "nanoid";
  import { afterUpdate, onMount, onDestroy } from "svelte";
  import { Group, Image as KonvaImage, Layer, Stage } from "svelte-konva";

  import { WarningModal, utils } from "@pixano/core";
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
  } from "@pixano/core";

  import {
    BBOX_STROKEWIDTH,
    INPUTPOINT_RADIUS,
    INPUTPOINT_STROKEWIDTH,
    INPUTRECT_STROKEWIDTH,
    MASK_STROKEWIDTH,
    POINT_SELECTION,
  } from "./lib/constants";
  import type { PolygonGroupDetails } from "./lib/types/canvas2dTypes";
  import {
    addMask,
    findOrCreateCurrentMask,
    clearCurrentAnn,
    mapMaskPointsToLineCoordinates,
  } from "./api/boundingBoxesApi";
  import PolygonGroup from "./components/PolygonGroup.svelte";
  import CreatePolygon from "./components/CreatePolygon.svelte";
  import Rectangle from "./components/Rectangle.svelte";

  // Exports
  export let selectedItem: DatasetItem;
  export let colorRange: string[] = ["0", "10"];
  export let masks: Mask[];
  export let bboxes: BBox[];
  export let embeddings: Record<string, ort.Tensor> = {};
  export let currentAnn: InteractiveImageSegmenterOutput | null = null;
  export let selectedTool: SelectionTool;
  export let newShape: Shape;

  let isReady = false;

  let colorScale: (id: string) => string;

  let viewEmbeddingModal = false;
  let viewWithoutEmbeddings = "";
  let numberOfBBoxes: number;
  let prevSelectedTool: SelectionTool;
  let zoomFactor: Record<string, number> = {}; // {viewId: zoomFactor}
  let manualMasks: PolygonGroupDetails[];
  $: manualMasks = mapMaskPointsToLineCoordinates(masks);

  $: {
    if (!prevSelectedTool?.isSmart || !selectedTool?.isSmart) {
      clearAnnotationAndInputs();
    }
    prevSelectedTool = selectedTool;
  }

  $: {
    if (newShape.status === "none" && newShape.shouldReset) {
      clearAnnotationAndInputs();
    }
  }

  $: {
    colorScale = utils.ordinalColorScale(colorRange);
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
  let images: Record<string, HTMLImageElement> = {}; // {viewId: HTMLImageElement}

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
      if (entry.target === stageContainer) {
        let width: number;
        let height: number;
        if (entry.contentBoxSize) {
          // Firefox implements `contentBoxSize` as a single ResizeObserverSize, rather than an array
          const contentBoxSize: ResizeObserverSize =
            entry.contentBoxSize instanceof ResizeObserverSize
              ? entry.contentBoxSize
              : entry.contentBoxSize[0];
          width = contentBoxSize.inlineSize;
          height = contentBoxSize.blockSize;
        } else {
          width = entry.contentRect.width;
          height = entry.contentRect.height;
        }
        stage.width(width);
        stage.height(height);
        stage.batchDraw();
      }
    }
  });

  // ********** INIT ********** //

  onMount(() => {
    loadItem();
    // Fire stage events observers
    resizeObserver.observe(stageContainer);
  });

  onDestroy(() => {
    clearAnnotationAndInputs();
  });

  afterUpdate(() => {
    if (currentId !== selectedItem.id) loadItem();

    if (selectedTool) {
      handleChangeTool();
    } else {
      // reset
      stage.container().style.cursor = "default";
    }
    if (currentAnn && currentAnn.validated) {
      validateCurrentAnn();
    }

    for (const viewId of Object.keys(selectedItem.views)) {
      const viewLayer: Konva.Layer = stage.findOne(`#${viewId}`);
      if (viewLayer) viewLayer.add(transformer);
    }
  });

  function loadItem() {
    // Calculate new grid size
    gridSize.cols = Math.ceil(Math.sqrt(Object.keys(selectedItem.views).length));
    gridSize.rows = Math.ceil(Object.keys(selectedItem.views).length / gridSize.cols);

    // Clear annotations in case a previous item was already loaded
    if (currentId) clearAnnotationAndInputs();

    for (const view of Object.values(selectedItem.views)) {
      zoomFactor[view.id] = 1;
      images[view.id] = new Image();
      images[view.id].src = `/${view.uri}` || view.url;
      images[view.id].onload = () => {
        // Find existing Konva elements in case a previous item was already loaded
        if (currentId) {
          const viewLayer: Konva.Layer = stage.findOne(`#${view.id}`);
          const konvaImg: Konva.Image = viewLayer.findOne(`#image-${view.id}`);
          konvaImg.image(images[view.id]);
        }
        scaleView(view);
        scaleElements(view);
        isReady = true;
        // hack to refresh view (display masks/bboxes)
        masks = masks;
        bboxes = bboxes;
      };
    }
    currentId = selectedItem.id;
  }

  function scaleView(view: ItemView) {
    const viewLayer: Konva.Layer = stage.findOne(`#${view.id}`);
    if (viewLayer) {
      // Calculate max dims for every image in the grid
      const maxWidth = stage.width() / gridSize.cols;
      const maxHeight = stage.height() / gridSize.rows;

      //calculate view pos in grid
      let i = 0;
      //get view index
      for (const viewId of Object.keys(selectedItem.views)) {
        if (viewId === view.id) break;
        i++;
      }
      const grid_pos = {
        x: i % gridSize.cols,
        y: Math.floor(i / gridSize.cols),
      };

      // Fit stage
      const scaleByHeight = maxHeight / images[view.id].height;
      const scaleByWidth = maxWidth / images[view.id].width;
      const scale = Math.min(scaleByWidth, scaleByHeight);
      //set zoomFactor for view
      zoomFactor[view.id] = scale;

      viewLayer.scale({ x: scale, y: scale });

      // Center view
      const offsetX = (maxWidth - images[view.id].width * scale) / 2 + grid_pos.x * maxWidth;
      const offsetY = (maxHeight - images[view.id].height * scale) / 2 + grid_pos.y * maxHeight;
      viewLayer.x(offsetX);
      viewLayer.y(offsetY);
    } else {
      console.log("Canvas2D.scaleView - Error: Cannot scale");
    }
  }

  function scaleElements(view: ItemView) {
    const viewLayer: Konva.Layer = stage.findOne(`#${view.id}`);

    // Scale input points
    const inputGroup: Konva.Group = viewLayer.findOne("#input");
    for (const point of inputGroup.children) {
      if (point instanceof Konva.Circle) {
        point.radius(INPUTPOINT_RADIUS / zoomFactor[view.id]);
        point.strokeWidth(INPUTPOINT_STROKEWIDTH / zoomFactor[view.id]);
      }
      if (point instanceof Konva.Rect) {
        point.strokeWidth(INPUTRECT_STROKEWIDTH / zoomFactor[view.id]);
      }
    }

    // Scale bboxes
    const bboxGroup: Konva.Group = viewLayer.findOne("#bboxes");
    if (!bboxGroup) return;
    for (const bboxKonva of bboxGroup.children) {
      if (bboxKonva instanceof Konva.Group) {
        for (const bboxElement of bboxKonva.children) {
          if (bboxElement instanceof Konva.Rect) {
            bboxElement.strokeWidth(BBOX_STROKEWIDTH / zoomFactor[view.id]);
          }
          if (bboxElement instanceof Konva.Label) {
            bboxElement.scale({
              x: 1 / zoomFactor[view.id],
              y: 1 / zoomFactor[view.id],
            });
          }
        }
      }
    }

    // Scale masks
    const maskGroup: Konva.Group = viewLayer.findOne("#masks");
    for (const maskKonva of maskGroup.children) {
      if (maskKonva instanceof Konva.Shape) {
        maskKonva.strokeWidth(MASK_STROKEWIDTH / zoomFactor[view.id]);
      }
    }
    const currentMaskGroup = findOrCreateCurrentMask(view.id, stage);
    for (const maskKonva of currentMaskGroup.children) {
      if (maskKonva instanceof Konva.Shape) {
        maskKonva.strokeWidth(MASK_STROKEWIDTH / zoomFactor[view.id]);
      }
    }
  }

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
      image: images[viewId],
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
          itemId: selectedItem.id,
          imageWidth: images[viewId].width,
          imageHeight: images[viewId].height,
          status: "inProgress",
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
    if (newShape?.status === "inProgress") return;
    const viewLayer: Konva.Layer = stage.findOne(`#${viewId}`);
    const cursorPositionOnImage = viewLayer.getRelativePointerPosition();
    const x = Math.round(cursorPositionOnImage.x);
    const y = Math.round(cursorPositionOnImage.y);

    const oldPoints = newShape.status === "creating" ? newShape.points : [];
    newShape = {
      status: "creating",
      type: "mask",
      points: [...oldPoints, { x, y, id: oldPoints.length || 0 }],
      viewId,
    };
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
    const inputGroup: Konva.Group = viewLayer.findOne("#input");
    for (const rect of inputGroup.children) {
      if (rect instanceof Konva.Rect) {
        //need to convert rect pos / size to topleft/bottomright
        const size = rect.size();
        const pos = rect.position();
        box = {
          x: pos.x,
          y: pos.y,
          width: size.width,
          height: size.height,
        };
        //we should have only one Box
        break;
      }
    }
    return box;
  }

  function dragInputRectMove(viewId: string) {
    if (selectedTool?.type === "RECTANGLE") {
      newShape = { status: "none" };
      const viewLayer: Konva.Layer = stage.findOne(`#${viewId}`);
      const inputGroup: Konva.Group = viewLayer.findOne("#input");
      const rect: Konva.Rect = inputGroup.findOne("#drag-rect");
      if (rect) {
        const pos = viewLayer.getRelativePointerPosition();
        rect.width(pos.x - rect.x());
        rect.size({
          width: pos.x - rect.x(),
          height: pos.y - rect.y(),
        });
      }
    }
  }

  async function dragInputRectEnd(viewId: string) {
    if (selectedTool?.type == "RECTANGLE") {
      const viewLayer: Konva.Layer = stage.findOne(`#${viewId}`);
      const inputGroup: Konva.Group = viewLayer.findOne("#input");
      const rect: Konva.Rect = inputGroup.findOne("#drag-rect");
      if (rect) {
        const { width, height } = rect.size();
        if (width == 0 || height == 0) {
          //rect with area = 0 -> delete it
          rect.destroy();
        } else {
          if (!selectedTool.isSmart) {
            newShape = {
              status: "inProgress",
              attrs: {
                x: rect.x(),
                y: rect.y(),
                width: rect.width(),
                height: rect.height(),
              },
              type: "rectangle",
              viewId,
              itemId: selectedItem.id,
              imageWidth: images[viewId].width,
              imageHeight: images[viewId].height,
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
    manualMasks = manualMasks.map((mask) =>
      mask.status === "created" ? mask : { ...mask, points: [] },
    );
    for (const viewId of Object.keys(selectedItem.views)) {
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
    if (newShape.status === "none") {
      console.log("salut");
      newShape = {
        status: "editing",
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
      const pos = viewLayer.getRelativePointerPosition();
      const inputGroup: Konva.Group = viewLayer.findOne("#input");
      //add RECT
      let rect: Konva.Rect = inputGroup.findOne("#drag-rect");
      if (rect) {
        rect.position({ x: pos.x, y: pos.y });
        rect.size({ width: 0, height: 0 });
      } else {
        rect = new Konva.Rect({
          id: "drag-rect",
          x: pos.x + 1,
          y: pos.y + 1,
          width: 0,
          height: 0,
          stroke: "hsl(316deg 60% 29.41%)",
          fill: "#f9f4f773",
          strokeWidth: INPUTRECT_STROKEWIDTH / zoomFactor[viewId],
          listening: false,
        });
        inputGroup.add(rect);
      }
      // TODO100: where magic happens
      viewLayer.on("pointermove", () => dragInputRectMove(viewId));
      viewLayer.on("pointerup", () => void dragInputRectEnd(viewId));
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

  function handleWheelOnImage(event: WheelEvent, view: ItemView) {
    // Prevent default scrolling
    event.preventDefault();

    // Get zoom direction
    let direction = event.deltaY < 0 ? 1 : -1;

    // Revert direction for trackpad
    if (event.ctrlKey) direction = -direction;

    // Zoom
    zoomFactor[view.id] = zoom(stage, direction, view.id);
    scaleElements(view);

    // Keep highlighted point scaling
    if (highlighted_point) highlightInputPoint(highlighted_point, view.id);
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
    if (event.key == "Escape") {
      clearAnnotationAndInputs();
    }
    if (event.key == "i") {
      console.log("Canvas2D - Infos");
      console.log("masks", masks);
      console.log("bboxes", bboxes);
      console.log("currentAnn", currentAnn);
      console.log("stage", stage);
      for (const viewId of Object.keys(selectedItem.views)) {
        const viewLayer: Konva.Layer = stage.findOne(`#${viewId}`);
        const maskGroup: Konva.Group = viewLayer.findOne("#masks");
        const bboxGroup: Konva.Group = viewLayer.findOne("#bboxes");
        console.log("masks Konva group:", maskGroup);
        console.log("masks children length:", maskGroup.children?.length);
        console.log("bboxes Konva group:", bboxGroup);
        console.log("bboxes children length:", bboxGroup.children?.length);
      }
    }
  }
</script>

<div
  class={cn("flex h-full w-full bg-slate-800 transition-opacity duration-300 delay-100", {
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
    {#each Object.values(selectedItem.views) as view}
      {#if images[view.id]}
        <Layer
          config={{ id: view.id }}
          on:wheel={(event) => handleWheelOnImage(event.detail.evt, view)}
        >
          <KonvaImage
            config={{ image: images[view.id], id: `image-${view.id}` }}
            on:pointerdown={(event) => handleClickOnImage(event.detail.evt, view.id)}
            on:pointerup={() => handlePointerUpOnImage(view.id)}
            on:dblclick={() => handleDoubleClickOnImage(view.id)}
          />
          <Group config={{ id: "currentAnnotation" }} />
          <Group config={{ id: "masks" }} />
          <Group config={{ id: "bboxes" }} />
          <Group config={{ id: "input" }} />
          {#each bboxes as bbox}
            {#if bbox.viewId === view.id}
              {#key bbox.id}
                <Rectangle
                  {bbox}
                  {colorScale}
                  zoomFactor={zoomFactor[view.id]}
                  {stage}
                  viewId={view.id}
                  bind:newShape
                />
              {/key}
            {/if}
          {/each}
          <CreatePolygon
            viewId={view.id}
            {stage}
            {images}
            {zoomFactor}
            selectedItemId={selectedItem.id}
            bind:newShape
          />
          {#each manualMasks as manualMask}
            {#key manualMask.id}
              {#if manualMask.viewId === view.id}
                <PolygonGroup
                  viewId={view.id}
                  bind:newShape
                  {stage}
                  {images}
                  {zoomFactor}
                  polygonDetails={manualMask}
                  color={colorScale(manualMask.id)}
                />
              {/if}
            {/key}
          {/each}
        </Layer>
      {/if}
    {/each}
    <Layer config={{ name: "tools" }} bind:handle={toolsLayer} />
  </Stage>
</div>
{#if viewEmbeddingModal}
  <WarningModal
    message="No embeddings found for view '{viewWithoutEmbeddings}'."
    on:confirm={() => (viewEmbeddingModal = false)}
  />
{/if}
<svelte:window on:keydown={handleKeyDown} />
