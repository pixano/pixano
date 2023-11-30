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
  import Konva from "konva";
  import shortid from "shortid";
  import { afterUpdate, onMount } from "svelte";
  import { Group, Image as KonvaImage, Layer, Stage } from "svelte-konva";

  import { WarningModal } from "@pixano/core";

  import { ToolType } from "./tools";

  import type {
    Tool,
    LabeledPointTool,
    RectangleTool,
    DeleteTool,
    PanTool,
    ClassificationTool,
  } from "./tools";
  import type { LabeledClick, Box, InteractiveImageSegmenterOutput } from "@pixano/models";
  import type { Mask, BBox, ItemData, ViewData } from "@pixano/core";
  import {
    BBOX_STROKEWIDTH,
    INPUTPOINT_RADIUS,
    INPUTPOINT_STROKEWIDTH,
    INPUTRECT_STROKEWIDTH,
    MASK_STROKEWIDTH,
  } from "./lib/constants";
  import {
    addBBox,
    addMask,
    destroyDeletedObjects,
    findOrCreateCurrentMask,
    clearCurrentAnn,
    toggleIsEditingBBox,
    toggleBBoxIsLocked,
  } from "./api/boundingBoxesApi";

  // Exports
  export let selectedItem: ItemData;
  export let selectedTool: Tool | null; // TODO100: refacto type here
  export let colorScale: (id: string) => string;
  export let masks: Array<Mask>;
  export let bboxes: Array<BBox>;

  export let embeddings = {};
  export let currentAnn: InteractiveImageSegmenterOutput | null = null;

  const short = shortid;

  let inferenceModelModal = false;
  let embeddingDirectoryModal = false;

  let zoomFactor: Record<string, number> = {}; // {viewId: zoomFactor}

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
          // Firefox implements `contentBoxSize` as a single content rect, rather than an array
          const contentBoxSize = Array.isArray(entry.contentBoxSize)
            ? entry.contentBoxSize[0]
            : entry.contentBoxSize;
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
      if (masks) updateMasks(viewId);
      if (bboxes) updateBboxes(viewId);
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
      images[view.id].src = view.uri;
      images[view.id].onload = () => {
        // Find existing Konva elements in case a previous item was already loaded
        if (currentId) {
          const viewLayer: Konva.Layer = stage.findOne(`#${view.id}`);
          const konvaImg: Konva.Image = viewLayer.findOne("#image");
          konvaImg.image(images[view.id]);
        }
        scaleView(view);
        scaleElements(view);
        //hack to refresh view (display masks/bboxes)
        masks = masks;
        bboxes = bboxes;
      };
    }
    currentId = selectedItem.id;
  }

  function scaleView(view: ViewData) {
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

  function scaleElements(view: ViewData) {
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

  function updateBboxes(viewId: string) {
    const viewLayer: Konva.Layer = stage.findOne(`#${viewId}`);

    if (viewLayer) {
      const bboxGroup: Konva.Group = viewLayer.findOne("#bboxes");
      const image: Konva.Image = viewLayer.findOne("#image");
      const bboxIds: Array<string> = [];

      if (!bboxGroup) return;

      for (let i = 0; i < bboxes.length; ++i) {
        if (bboxes[i].viewId === viewId) {
          bboxIds.push(bboxes[i].id);

          //don't add a bbox that already exist
          const bboxKonva: Konva.Group = bboxGroup.findOne(`#${bboxes[i].id}`);
          if (!bboxKonva) {
            addBBox(
              bboxes[i],
              colorScale(bboxes[i].catId.toString()),
              bboxGroup,
              image,
              viewId,
              zoomFactor,
              (val) => {
                bboxes = toggleIsEditingBBox(val, stage, bboxes[i], bboxes);
              },
            );
          } else {
            toggleIsEditingBBox(bboxes[i].editing ? "on" : "off", stage, bboxes[i], bboxes);
            toggleBBoxIsLocked(stage, bboxes[i]);
            //update visibility & opacity
            bboxKonva.visible(bboxes[i].visible);
            bboxKonva.opacity(bboxes[i].opacity);
            //update color
            const style = new Option().style;
            style.color = colorScale(bboxes[i].catId.toString());
            for (const bboxElement of bboxKonva.children) {
              if (bboxElement instanceof Konva.Rect) {
                bboxElement.stroke(style.color);
              }
              if (bboxElement instanceof Konva.Label) {
                bboxElement.getTag().fill(style.color);
                bboxElement.getTag().stroke();
              }
            }
          }
        }
      }

      destroyDeletedObjects(bboxIds, bboxGroup);
    }
  }

  function updateMasks(viewId: string) {
    const viewLayer: Konva.Layer = stage.findOne(`#${viewId}`);

    if (viewLayer) {
      const maskGroup: Konva.Group = viewLayer.findOne("#masks");
      const image: Konva.Image = viewLayer.findOne("#image");
      const maskIds: Array<string> = [];

      for (let i = 0; i < masks.length; ++i) {
        if (masks[i].viewId === viewId) {
          maskIds.push(masks[i].id);

          //don't add a mask that already exist
          const maskKonva: Konva.Shape = maskGroup.findOne(`#${masks[i].id}`);
          if (!maskKonva) {
            addMask(
              masks[i],
              colorScale(masks[i].catId.toString()),
              maskGroup,
              image,
              viewId,
              stage,
              zoomFactor,
            );
          } else {
            //update visibility & opacity
            maskKonva.visible(masks[i].visible);
            maskKonva.opacity(masks[i].opacity);
            //update color
            const style = new Option().style;
            style.color = colorScale(masks[i].catId.toString());
            maskKonva.stroke(style.color);
            maskKonva.fill(`rgba(${style.color.replace("rgb(", "").replace(")", "")}, 0.35)`);
          }
        }
      }

      destroyDeletedObjects(maskIds, maskGroup);
    }
  }

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
      inferenceModelModal = true;
      clearAnnotationAndInputs();
    } else if (!(viewId in embeddings) || (viewId in embeddings && embeddings[viewId] == null)) {
      embeddingDirectoryModal = true;
      clearAnnotationAndInputs();
    } else {
      const results = await selectedTool.postProcessor.segmentImage(input);
      if (results) {
        const currentMaskGroup = findOrCreateCurrentMask(viewId, stage);
        const viewLayer: Konva.Layer = stage.findOne(`#${viewId}`);
        const image: Konva.Image = viewLayer.findOne("#image");

        // always clean existing masks before adding a new currentAnn
        currentMaskGroup.removeChildren();

        const new_id = short.generate();
        currentAnn = {
          id: `${new_id}`,
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
      case ToolType.LabeledPoint:
        displayInputPointTool(selectedTool as LabeledPointTool);
        break;
      case ToolType.Rectangle:
        displayInputRectTool(selectedTool as RectangleTool);
        // Enable box creation or change cursor style
        break;
      case ToolType.Delete:
        clearAnnotationAndInputs();
        displayInputDeleteTool(selectedTool as DeleteTool);
        break;
      case ToolType.Pan:
        displayPanTool(selectedTool as PanTool);
        // Enable box creation or change cursor style
        break;
      case ToolType.Classification:
        displayClassificationTool(selectedTool as ClassificationTool);
        break;

      default:
        // Reset or disable any specific behavior
        break;
    }
  }

  function clearInputs(viewId: string) {
    const viewLayer: Konva.Layer = stage.findOne(`#${viewId}`);
    const inputGroup: Konva.Group = viewLayer.findOne("#input");
    inputGroup.destroyChildren();
  }

  // ********** PAN TOOL ********** //

  function displayPanTool(tool: PanTool) {
    if (toolsLayer) {
      //clean other tools
      //TODO: etre générique sur l'ensemble des outils != Pan
      const pointer = stage.findOne(`#${ToolType.LabeledPoint}`);
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

  function displayClassificationTool(tool: ClassificationTool) {
    if (toolsLayer) {
      //clean other tools
      //TODO: etre générique sur l'ensemble des outils != Pan
      const pointer = stage.findOne(`#${ToolType.LabeledPoint}`);
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
      let zoomF = 1.0; //in some cases we aren't in a view, so we use default scaling
      if (viewId) zoomF = zoomFactor[viewId];
      pointer = new Konva.Circle({
        id: id,
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

  async function dragInputPointMove(drag_point: Konva.Circle, viewId: string) {
    stage.container().style.cursor = "grabbing";

    const viewLayer: Konva.Layer = stage.findOne(`#${viewId}`);
    const image: Konva.Image = viewLayer.findOne("#image");
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
    await updateCurrentMask(viewId);
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

  function displayInputRectTool(tool: RectangleTool) {
    if (toolsLayer) {
      //clean other tools
      //TODO: etre générique sur l'ensemble des outils != Rectangle
      const pointer = stage.findOne(`#${ToolType.LabeledPoint}`);
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
    if (selectedTool?.type == ToolType.Rectangle) {
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
    if (selectedTool?.type == ToolType.Rectangle) {
      const viewLayer: Konva.Layer = stage.findOne(`#${viewId}`);
      const inputGroup: Konva.Group = viewLayer.findOne("#input");
      const rect: Konva.Rect = inputGroup.findOne("#drag-rect");
      if (rect) {
        const { width, height } = rect.size();
        if (width == 0 || height == 0) {
          //rect with area = 0 -> delete it
          rect.destroy();
        } else {
          //predict
          // TODO100 : RECT : SAVE RECTANGLE HERE
          // !selectedTool.isSmart && (rectangles = [...rectangles, { ...rect.attrs }]); // TODO100: better conditionning here
          selectedTool.isSmart && (await updateCurrentMask(viewId)); // SMART RECTANGLE ONLY
        }
        viewLayer.off("pointermove");
        viewLayer.off("pointerup");
      }
    }
  }

  // ********** INPUT DELETE TOOL ********** //

  function displayInputDeleteTool(tool: DeleteTool) {
    if (toolsLayer) {
      //clean other tools
      //TODO: etre générique sur l'ensemble des outils != DELETE
      const pointer = stage.findOne(`#${ToolType.LabeledPoint}`);
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
    for (const viewId of Object.keys(selectedItem.views)) {
      clearInputs(viewId);
      clearCurrentAnn(viewId, stage, selectedTool);
    }
    stage.container().style.cursor = selectedTool.cursor;
    currentAnn = null;
  }

  // ********** MOUSE EVENTS ********** //

  function handleMouseMoveStage() {
    const position = stage.getRelativePointerPosition();

    // Update tools states
    if (selectedTool?.type == ToolType.LabeledPoint) {
      updateInputPointStage(position);
    }

    if (selectedTool?.type == ToolType.Rectangle) {
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

  async function handleClickOnImage(event: CustomEvent, viewId: string) {
    const viewLayer: Konva.Layer = stage.findOne(`#${viewId}`);
    // Perform tool action if any active tool
    // For convenience: bypass tool on mouse middle-button click
    if (selectedTool?.type == ToolType.Pan || event.detail.evt.which == 2) {
      viewLayer.draggable(true);
      viewLayer.on("dragmove", handleMouseMoveStage);
      viewLayer.on("dragend", () => handleDragEndOnView(viewId));
    } else if (selectedTool?.type == ToolType.LabeledPoint) {
      const clickOnViewPos = viewLayer.getRelativePointerPosition();

      //add Konva Point
      const input_point = new Konva.Circle({
        name: `${(selectedTool as LabeledPointTool).label}`,
        x: clickOnViewPos.x,
        y: clickOnViewPos.y,
        radius: INPUTPOINT_RADIUS / zoomFactor[viewId],
        stroke: "white",
        fill: (selectedTool as LabeledPointTool).label === 1 ? "green" : "red",
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
    } else if (selectedTool?.type == ToolType.Rectangle) {
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
          stroke: "white",
          dash: [10, 5],
          fill: "rgba(255, 255, 255, 0.15)",
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

  function handleWheelOnImage(event: CustomEvent, view: ViewData) {
    event.detail.evt.preventDefault(); // Prevent default scrolling
    let direction = event.detail.evt.deltaY < 0 ? 1 : -1; // Get zoom direction
    // When we zoom on trackpad, e.evt.ctrlKey is true
    // In that case lets revert direction.
    if (event.detail.evt.ctrlKey) direction = -direction;
    zoomFactor[view.id] = zoom(stage, direction, view.id);
    scaleElements(view);

    //zoom reset highlighted point scaling
    if (highlighted_point) {
      highlightInputPoint(highlighted_point, view.id);
    }
  }

  function handleLayerClick(viewId: string) {
    const viewLayer: Konva.Layer = stage.findOne(`#${viewId}`);
    const allBBoxes: Konva.Group = viewLayer.findOne("#bboxes");
    allBBoxes.children.forEach((bbox) => {
      bboxes = toggleIsEditingBBox(
        "off",
        stage,
        bboxes.find((b) => b.id === bbox.id()),
        bboxes,
      );
    });
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

<div class="flex h-full w-full bg-slate-100" bind:this={stageContainer}>
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
          on:wheel={(event) => handleWheelOnImage(event, view)}
          on:click={() => handleLayerClick(view.id)}
        >
          <KonvaImage
            config={{ image: images[view.id], id: "image" }}
            on:pointerdown={(event) => handleClickOnImage(event, view.id)}
            on:pointerup={() => handlePointerUpOnImage(view.id)}
            on:dblclick={() => handleDoubleClickOnImage(view.id)}
          />
          <Group config={{ id: "currentAnnotation" }} />
          <Group config={{ id: "masks" }} />
          <Group config={{ id: "bboxes" }} />
          <Group config={{ id: "input" }} />
        </Layer>
      {/if}
    {/each}
    <Layer config={{ name: "tools" }} bind:handle={toolsLayer} />
  </Stage>
</div>
{#if inferenceModelModal}
  <WarningModal
    message="No interactive model set up, cannot segment."
    details="Please refer to our interactive annotation notebook for information on how to export your model to ONNX."
    on:confirm={() => (inferenceModelModal = false)}
  />
{/if}
{#if embeddingDirectoryModal}
  <WarningModal
    message="No embedding directory found, cannot segment."
    details="Please refer to our interactive annotation notebook for information on how to precompute embeddings on your dataset."
    on:confirm={() => (embeddingDirectoryModal = false)}
  />
{/if}
<svelte:window on:keydown={handleKeyDown} />
