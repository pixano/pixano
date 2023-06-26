<script lang="ts">
  /**
    @copyright CEA-LIST/DIASI/SIALV/LVA (2023)
    @author CEA-LIST/DIASI/SIALV/LVA <pixano@cea.fr>
    @license CECILL-C

    This software is a collaborative computer program whose purpose is to
    generate and explore labeled data for computer vision applications.
    This software is governed by the CeCILL-C license under French law and
    abiding by the rules of distribution of free software. You can use, 
    modify and/ or redistribute the software under the terms of the CeCILL-C
    license as circulated by CEA, CNRS and INRIA at the following URL

    http://www.cecill.info
    */

  // Imports
  import { afterUpdate, onMount } from "svelte";
  import { Stage, Layer, Group, Image as KonvaImage } from "svelte-konva";
  import Konva from "konva";
  import { zoom } from "../../core/src/konva_utils";
  import { getColor } from "../../core/src/utils";

  import { ToolType, type PanTool } from "./tools";
  import type { Tool, LabeledPointTool, RectangleTool } from "./tools";
  import type {
    LabeledClick,
    Box,
    InteractiveImageSegmenterOutput,
  } from "../../models/src/interactive_image_segmentation";
  import type { AnnotationsLabels, MaskGT, BBox, ViewData } from "./interfaces";

  const POINTER_RADIUS: number = 6;
  const POINTER_STROKEWIDTH: number = 3;
  const RECT_STROKEWIDTH: number = 1.5;
  let zoomFactor = {}; //dict of zoomFactors by viewId {viewId: zoomFactor}
  let timerId;

  // Inputs
  export let embedding: any = null;
  export let imageId: string;
  export let views: Array<ViewData>;

  export let masksGT: Array<MaskGT> | null;
  export let bboxes: Array<BBox> | null;
  export let annotations: Array<AnnotationsLabels>;

  //let prevImg: string = "";
  //export let imageEmbedding = null;
  export let selectedTool: Tool | null;

  // Output
  export let prediction: InteractiveImageSegmenterOutput | null;

  // References to HTML Elements
  let stageContainer: HTMLElement;
  let images: Record<string, HTMLImageElement> = {}; //dict {viewId: HTMLImageElement}

  // References to Konva Elements
  let stage: Konva.Stage;
  let toolsLayer: Konva.Layer;
  // let imageKonva: Konva.Image;
  let highlighted_point: Konva.Circle = null;

  let oldId: string;
  // Function that maps an id to a color
  let categoryColor = null;

  // Main konva stage configuration
  let stageConfig: Konva.ContainerConfig = {
    width: 1024,
    height: 780,
    name: "konva",
  };

  // Multiview image grid
  let gridSize = {
    rows: 0,
    cols: 0,
  };

  let prev_views: Array<ViewData>;

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

  async function onLoadViewImage(event, viewId: string) {
    images[viewId] = event.target;
  }

  function scaleView(view: ViewData) {
    const view_layer = stage.findOne(`#${view.viewId}`) as Konva.Layer;
    if (view_layer) {
      // Calculate max dims for every image in the grid
      let maxWidth = stage.width() / gridSize.cols;
      let maxHeight = stage.height() / gridSize.rows;

      //calculate view pos in grid
      let i = 0;
      //get view index
      for (let v of views) {
        if (v.viewId === view.viewId) break;
        i++;
      }
      let grid_pos = {
        x: i % gridSize.cols,
        y: Math.floor(i / gridSize.cols),
      };

      // Fit stage
      let scaleByHeight = maxHeight / images[view.viewId].height;
      let scaleByWidth = maxWidth / images[view.viewId].width;
      let scale = Math.min(scaleByWidth, scaleByHeight);
      //set zoomFactor for view
      zoomFactor[view.viewId] = scale;

      view_layer.scale({ x: scale, y: scale });

      // Center view
      let offsetX =
        (maxWidth - images[view.viewId].width * scale) / 2 +
        grid_pos.x * maxWidth;
      let offsetY =
        (maxHeight - images[view.viewId].height * scale) / 2 +
        grid_pos.y * maxHeight;
      view_layer.x(offsetX);
      view_layer.y(offsetY);
    } else {
      console.log("   CANNOT scale");
    }
  }

  // Init
  onMount(() => {
    //console.log(`selected tool ${selectedTool?.type}`);

    // Load Image(s)
    for (let view of views) {
      zoomFactor[view.viewId] = 1;
      const img = new Image();
      img.src = view.imageURL;
      img.onload = (event) => {
        onLoadViewImage(event, view.viewId).then(() => {
          scaleView(view);
          //hack to refresh view (display masks/bboxes)
          masksGT = masksGT;
        });
      };
    }
    categoryColor = getColor(annotations.map((it) => it.category_id)); // Define a color map for each category id
    prev_views = views;

    // Calculate new grid size
    gridSize.cols = Math.ceil(Math.sqrt(views.length));
    gridSize.rows = Math.ceil(views.length / gridSize.cols);

    // Fire stage events observers
    resizeObserver.observe(stageContainer);
  });

  function resetStage() {
    //find groups for all views
    let inputs = stage.find("#input") as Array<Konva.Group>;
    let maskss = stage.find("#masks") as Array<Konva.Group>;
    let bboxess = stage.find("#bboxes") as Array<Konva.Group>;

    //destroy all
    for (let input of inputs) input.destroyChildren();
    for (let masks of maskss) masks.destroyChildren();
    for (let bboxes of bboxess) bboxes.destroyChildren();
  }

  afterUpdate(() => {
    if (selectedTool) {
      handleToolChange();
    } else {
      // reset
      stage.container().style.cursor = "default";
    }
    if (prediction && prediction.validated) {
      handleMaskValidated(prediction.viewId);
    }
    if (masksGT) {
      for (let view of views) addMaskGT(view.viewId, imageId);
    }
    if (bboxes) {
      for (let view of views) addAllBBox(view.viewId, imageId);
    }

    if (views !== prev_views) {
      // Reset stage
      resetStage();

      // Load Image(s)
      for (let view of views) {
        const view_layer = stage.findOne(`#${view.viewId}`) as Konva.Layer;
        zoomFactor[view.viewId] = 1;
        const img = new Image();
        img.src = view.imageURL;
        img.onload = (event) => {
          onLoadViewImage(event, view.viewId).then(() => {
            const konvaImg = view_layer.findOne(`#${imageId}`) as Konva.Image;
            konvaImg.image(img);
            scaleView(view);
            //hack to refresh view (display masks/bboxes)
            masksGT = masksGT;
          });
        };
      }
      categoryColor = getColor(annotations.map((it) => it.category_id)); // Define a color map for each category id
      prev_views = views;
    }
  });

  function getBox(viewId): Box {
    //get box as Box
    let box: Box = null;
    const view_layer = stage.findOne(`#${viewId}`) as Konva.Layer;
    let input_group: Konva.Group = view_layer.findOne("#input");
    for (let rect of input_group.children) {
      if (rect instanceof Konva.Rect) {
        //need to convert rect pos / size to topleft/bottomright
        let size = rect.size();
        let pos = rect.position();
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

  function getAllClicks(viewId): Array<LabeledClick> {
    //get points as Array<LabeledClick>
    let points: Array<LabeledClick> = [];
    const view_layer = stage.findOne(`#${viewId}`) as Konva.Layer;
    let input_group: Konva.Group = view_layer.findOne("#input");
    for (let pt of input_group.children) {
      if (pt instanceof Konva.Circle) {
        let lblclick: LabeledClick = {
          x: pt.x(),
          y: pt.y(),
          label: parseInt(pt.name()),
        };
        points.push(lblclick);
      }
    }
    return points;
  }

  function clearInputs(viewId) {
    const view_layer = stage.findOne(`#${viewId}`) as Konva.Layer;
    const input_group = view_layer.findOne("#input") as Konva.Group;
    input_group.destroyChildren();
  }

  function clearCurrentMask(viewId) {
    const view_layer = stage.findOne(`#${viewId}`) as Konva.Layer;
    let masks: Konva.Group = view_layer.findOne("#masks");
    let predictedMasks = masks.findOne("#predictedMasks") as Konva.Group;
    if (predictedMasks) predictedMasks.destroy();
  }

  function addAllBBox(viewId, imageId) {
    const view_layer: Konva.Layer = stage.findOne(`#${viewId}`);

    if (view_layer) {
      const group: Konva.Group = view_layer.findOne("#bboxes");
      const image: Konva.Image = view_layer.findOne(`#${imageId}`);

      const listBboxIds = [];
      for (let i = 0; i < bboxes.length; ++i) {
        if (bboxes[i].viewId === viewId) {
          listBboxIds.push(bboxes[i].id);

          //don't add a mask that already exist
          let bbox = group.findOne(`#${bboxes[i].id}`);
          if (!bbox) {
            addBBox(bboxes[i], image, categoryColor?.(bboxes[i].catID), group);
          } else {
            //apply visibility
            bbox.visible(bboxes[i].visible);
          }
        }
      }

      //remove masks that's no longer exist in masksGT
      for (let bbox of group.children) {
        if (!listBboxIds.includes(bbox.id())) {
          bbox.destroy();
        }
      }
    }
  }

  function addBBox(
    bbox: BBox,
    image: Konva.Image,
    color: any,
    group: Konva.Group
  ) {
    const img_w = (image.image() as HTMLImageElement).naturalWidth;
    const img_h = (image.image() as HTMLImageElement).naturalHeight;
    const rect_x = image.x() + bbox.bbox[0] * img_w;
    const rect_y = image.y() + bbox.bbox[1] * img_h;
    const rect_width = bbox.bbox[2] * img_w;
    const rect_height = bbox.bbox[3] * img_h;

    const bbox_group = new Konva.Group({
      id: bbox.id,
      visible: bbox.visible,
      listening: false,
    });

    const kbbox = new Konva.Rect({
      //TMP: height et width sont inversés car parquet généré avec normalisation inversés
      //(because on a remplacé un normalize(w,h) par un normalize(h,w)...)
      //dès qu'un nouveau package permettant de générer correctement les bbox est ready je rebascule
      x: rect_x,
      y: rect_y,
      width: rect_width,
      height: rect_height,
      stroke: color,
      strokeWidth: 1.0,
      scale: image.scale(),
    });
    bbox_group.add(kbbox);

    // Create a label object
    const label = new Konva.Label({
      x: rect_x,
      y: rect_y,
    });

    // Add a tag to the label
    label.add(
      new Konva.Tag({
        fill: color,
        stroke: color,
      })
    );

    // Add some text to the label
    label.add(
      new Konva.Text({
        text: bbox.label,
        fontSize: 6,
        fontStyle: "bold",
        padding: 0,
        x: rect_x,
        y: rect_y,
      })
    );

    // Add the label to the group
    bbox_group.add(label);

    group.add(bbox_group);
  }

  /**
     * Add set of mask to its specific group
        if (results) {
    */
  function addMask(
    masksSVG: Array<string>,
    id: string,
    x: number,
    y: number,
    scale: Konva.Vector2d,
    stroke: string,
    visibility: boolean,
    opacity: number,
    group: Konva.Group
  ) {
    let fill: string;
    switch (stroke) {
      case "green":
        fill = "rgba(0, 255, 0, 0.25)";
        break;
      case "blue":
        fill = "rgba(0, 0, 255, 0.25)";
        break;
      default:
        var s = new Option().style;
        s.color = stroke;
        if (s.color !== "") {
          fill = `rgba(${s.color.replace("rgb(", "").replace(")", "")}, 0.35)`;
        } else {
          fill = "rgba(255, 255, 255, 0.35)";
        }
        break;
    }
    //utility functions to extract coords from SVG
    //works only with SVG format "Mx0 y0 Lx1 y1 ... xn yn"
    // --> format generated by convertSegmentsToSVG
    function m_part(svg: string) {
      const splits = svg.split(" ");
      const x = splits[0].slice(1); //remove "M"
      return { x: parseInt(x), y: parseInt(splits[1]) };
    }
    function l_part(svg: string) {
      const splits = svg.split(" ");
      const x0 = splits[2].slice(1); //remove "L"
      const res = [{ x: parseInt(x0), y: parseInt(splits[3]) }];
      for (let i = 4; i < splits.length; i += 2) {
        res.push({
          x: parseInt(splits[i]),
          y: parseInt(splits[i + 1]),
        });
      }
      return res;
    }
    const mask = new Konva.Shape({
      id: id,
      x: x,
      y: y,
      width: stage.width(),
      height: stage.height(),
      fill: fill,
      stroke: stroke,
      scale: scale,
      visible: visibility,
      opacity: opacity,
      listening: false,
      sceneFunc: (ctx, shape) => {
        ctx.beginPath();
        for (let i = 0; i < masksSVG.length; ++i) {
          const start = m_part(masksSVG[i]);
          ctx.moveTo(start.x, start.y);
          const l_pts = l_part(masksSVG[i]);
          for (let pt of l_pts) {
            ctx.lineTo(pt.x, pt.y);
          }
        }
        ctx.fillStrokeShape(shape);
      },
    });
    group.add(mask);
  }

  function findOrCreatePredictedMaskGroup(viewId): Konva.Group {
    const view_layer = stage.findOne(`#${viewId}`) as Konva.Layer;

    // findOrCreate mask group;
    let masks: Konva.Group = view_layer.findOne("#masks");

    // Get and update the current predicted masks
    let predictedMasksGroup = masks.findOne("#predictedMasks") as Konva.Group;

    if (!predictedMasksGroup) {
      predictedMasksGroup = new Konva.Group({
        id: "predictedMasks",
      });
      masks.add(predictedMasksGroup);
    }
    return predictedMasksGroup;
  }

  async function addMaskPrediction(imageId, viewId) {
    const points = getAllClicks(viewId);
    const box = getBox(viewId);
    const input = {
      image: images[viewId],
      embedding: embedding,
      points: points,
      box: box,
    };

    if (selectedTool.postProcessor == null) {
      console.log("No segmentation model connected, cannot segment");
    } else if (embedding == null) {
      console.log("No embeddings, cannot segment");
    } else {
      const results = await selectedTool.postProcessor.segmentImage(input);
      if (results) {
        const group = findOrCreatePredictedMaskGroup(viewId);
        const view_layer = stage.findOne(`#${viewId}`) as Konva.Layer;
        const image = view_layer.findOne(`#${imageId}`);

        // always clean existing masks before adding a new prediction
        group.removeChildren();
        const new_id = Math.floor(Math.random() * 5000).toString(); //TODO use shortuiid instead
        prediction = {
          id: new_id,
          viewId: viewId,
          label: "",
          catID: -1,
          output: results,
          input_points: points,
          input_box: box,
          validated: false,
        };
        addMask(
          results.masksImageSVG,
          new_id,
          image.x(),
          image.y(),
          image.scale(),
          "green",
          true,
          1.0,
          group
        );
      }
    }
  }

  function addMaskGT(viewId, imageId) {
    const view_layer: Konva.Layer = stage.findOne(`#${viewId}`);

    if (view_layer) {
      const group: Konva.Group = view_layer.findOne("#masksGT");
      const image = view_layer.findOne(`#${imageId}`);

      const listMaskGTIds = [];
      for (let i = 0; i < masksGT.length; ++i) {
        listMaskGTIds.push(masksGT[i].id);
        if (masksGT[i].viewId === viewId) {
          //don't add a mask that already exist
          let mask = group.findOne(`#${masksGT[i].id}`);
          if (!mask) {
            addMask(
              masksGT[i].mask,
              masksGT[i].id,
              image.x(),
              image.y(),
              image.scale(),
              categoryColor?.(masksGT[i].catID),
              masksGT[i].visible,
              1.0,
              group
            );
          } else {
            //update visibility & opacity
            mask.visible(masksGT[i].visible);
            mask.opacity(masksGT[i].opacity);
          }
        }
      }

      //remove masks that's no longer exist in masksGT
      for (let mask of group.children) {
        if (!listMaskGTIds.includes(mask.id())) {
          mask.destroy();
        }
      }
    }
  }

  // Events Handlers
  function handleMaskValidated(viewId) {
    if (prediction.validated) {
      const view_layer = stage.findOne(`#${viewId}`) as Konva.Layer;
      let predictedMasks = findOrCreatePredictedMaskGroup(viewId);
      if (predictedMasks) {
        //move predictedMasks to maskGT
        const masksGT_group: Konva.Group = view_layer.findOne("#masksGT");
        predictedMasks.id(prediction.id);
        // change color  //TODO: use table of color by class or whatever
        for (let s of predictedMasks.children) {
          console.log(categoryColor?.(prediction.catID));
          let shape = s as Konva.Shape;
          var pred = new Option().style;
          pred.color = categoryColor?.(prediction.catID);
          shape.fill(
            `rgba(${pred.color.replace("rgb(", "").replace(")", "")}, 0.35)`
          );
          shape.stroke(pred.color);
        }
        predictedMasks.moveTo(masksGT_group);
        masksGT.push({
          viewId: viewId,
          id: prediction.id,
          mask: prediction.output.masksImageSVG,
          rle: prediction.output.rle,
          catID: prediction.catID,
          visible: true,
          opacity: 1.0,
        });

        clearInputs(prediction.viewId);
        prediction = null;
      }
    }
  }

  function handleToolChange() {
    //make sure tools layer is on front
    if (toolsLayer) toolsLayer.moveToTop();

    // Update the behavior of the canvas stage based on the selected tool
    // You can add more cases for different tools as needed
    switch (selectedTool.type) {
      case ToolType.LabeledPoint:
        displayLabeledPointCreator(selectedTool as LabeledPointTool);
        break;
      case ToolType.Rectangle:
        displayRectangleCreator(selectedTool as RectangleTool);
        // Enable box creation or change cursor style
        break;
      case ToolType.Pan:
        displayPanMode(selectedTool as PanTool);
        // Enable box creation or change cursor style
        break;
      default:
        // Reset or disable any specific behavior
        break;
    }
  }

  // Stage events Handlers
  function handleMouseMoveStage() {
    const position = stage.getRelativePointerPosition();

    // Update tools states
    if (selectedTool?.type == ToolType.LabeledPoint) {
      updateLabeledPointToolState(position);
    }

    if (selectedTool?.type == ToolType.Rectangle) {
      updateRectangleToolState(position);
    }
  }

  function handleMouseEnterStage(event) {
    for (let tool of toolsLayer.children) {
      tool.show();
    }
  }
  function handleMouseLeaveStage(event) {
    for (let tool of toolsLayer.children) {
      tool.hide();
    }
  }

  // Views events Handlers
  function handleDragMoveOnView() {
    handleMouseMoveStage();
  }

  function handleDragEndOnView(viewId: string) {
    const view_layer = stage.findOne(`#${viewId}`);
    view_layer.draggable(false);
    view_layer.off("dragend dragmove");
  }

  function handlePointerUpOnImage(event, viewId: string) {
    const view_layer = stage.findOne(`#${viewId}`);
    view_layer.draggable(false);
    view_layer.off("dragend dragmove");
    if (highlighted_point) {
      //hack to unhiglight when we drag while predicting...
      //try to determine if we are still on highlighted point
      //Note: could be better, but usually it will work
      const pos = view_layer.getRelativePointerPosition();
      const hl_pos = highlighted_point.position();
      if (pos.x !== hl_pos.x || pos.y !== hl_pos.y)
        unhighlightPoint(highlighted_point, viewId);
    }
  }

  function scaleInputs(viewId) {
    //keep points/box at constant scale
    const view_layer = stage.findOne(`#${viewId}`) as Konva.Layer;
    const input_group = view_layer.findOne("#input") as Konva.Group;
    for (let pt of input_group.children) {
      if (pt instanceof Konva.Circle) {
        pt.radius(POINTER_RADIUS / zoomFactor[viewId]);
        pt.strokeWidth(POINTER_STROKEWIDTH / zoomFactor[viewId]);
      }
      if (pt instanceof Konva.Rect) {
        pt.strokeWidth(RECT_STROKEWIDTH / zoomFactor[viewId]);
      }
    }
  }

  function handleWheelOnImage(event, viewId: string) {
    event.detail.evt.preventDefault(); // Prevent default scrolling
    let direction = event.detail.evt.deltaY < 0 ? 1 : -1; // Get zoom direction
    // When we zoom on trackpad, e.evt.ctrlKey is true
    // In that case lets revert direction.
    if (event.detail.evt.ctrlKey) direction = -direction;
    zoomFactor[viewId] = zoom(stage, direction, viewId);
    scaleInputs(viewId);

    //zoom reset highlighted point scaling
    if (highlighted_point) {
      highlightPoint(highlighted_point, viewId);
    }
  }

  function handleDblClickOnImage(event, viewId: string) {
    // put double-clickd view on top of views
    const view_layer = stage.findOne(`#${viewId}`) as Konva.Layer;
    view_layer.moveToTop();
    //keeps tools on top
    toolsLayer.moveToTop();
  }

  async function handleClickOnImage(event, imageId: string, viewId: string) {
    const view_layer = stage.findOne(`#${viewId}`) as Konva.Layer;
    // Perfome tool action if any active tool
    // For convenience: bypass tool on mouse middle-button click
    if (selectedTool?.type == ToolType.Pan || event.detail.evt.which == 2) {
      view_layer.draggable(true);
      view_layer.on("dragmove", handleDragMoveOnView);
      view_layer.on("dragend", () => handleDragEndOnView(viewId));
    } else if (selectedTool?.type == ToolType.LabeledPoint) {
      const clickOnViewPos = view_layer.getRelativePointerPosition();

      //add Konva Point
      const input_point = new Konva.Circle({
        name: `${(selectedTool as LabeledPointTool).label}`,
        x: clickOnViewPos.x,
        y: clickOnViewPos.y,
        radius: POINTER_RADIUS / zoomFactor[viewId],
        stroke: "white",
        fill: (selectedTool as LabeledPointTool).label === 1 ? "green" : "red",
        strokeWidth: POINTER_STROKEWIDTH / zoomFactor[viewId],
        visible: true,
        listening: true,
        opacity: 0.75,
        draggable: true,
      });
      input_point.on("pointerenter", (event) =>
        highlightPoint(event.target as Konva.Circle, viewId)
      );
      input_point.on("pointerout", (event) =>
        unhighlightPoint(event.target as Konva.Circle, viewId)
      );
      input_point.on("dragmove", (event) =>
        dragPointMove(event.target as Konva.Circle, imageId, viewId)
      );
      input_point.on("dragend", (event) =>
        dragPointEnd(event.target as Konva.Circle, viewId)
      );
      const input_group = view_layer.findOne("#input") as Konva.Group;
      input_group.add(input_point);
      highlightPoint(input_point, viewId);

      addMaskPrediction(imageId, viewId);
    } else if (selectedTool?.type == ToolType.Rectangle) {
      const pos = view_layer.getRelativePointerPosition();
      const input_group = view_layer.findOne("#input") as Konva.Group;

      //add RECT
      let rect = input_group.findOne("#drag-rect") as Konva.Rect;
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
          fill: "rgba(255, 255, 255, 0.25)",
          strokeWidth: RECT_STROKEWIDTH / zoomFactor[viewId],
          listening: false,
        });
        input_group.add(rect);
      }
      view_layer.on("pointermove", () => handleToolBoxDragMove(viewId));
      view_layer.on("pointerup", () => handleToolBoxDragEnd(viewId));
    }
  }

  function handleToolBoxDragMove(viewId: string) {
    if (selectedTool?.type == ToolType.Rectangle) {
      const view_layer = stage.findOne(`#${viewId}`) as Konva.Layer;
      const input_group = view_layer.findOne("#input") as Konva.Group;
      const rect = input_group.findOne("#drag-rect") as Konva.Rect;
      if (rect) {
        const pos = view_layer.getRelativePointerPosition();
        rect.width(pos.x - rect.x());
        rect.size({
          width: pos.x - rect.x(),
          height: pos.y - rect.y(),
        });
      }
    }
  }

  function handleToolBoxDragEnd(viewId: string): void {
    if (selectedTool?.type == ToolType.Rectangle) {
      const view_layer = stage.findOne(`#${viewId}`) as Konva.Layer;
      const input_group = view_layer.findOne("#input") as Konva.Group;
      const rect = input_group.findOne("#drag-rect") as Konva.Rect;
      if (rect) {
        const { width, height } = rect.size();
        if (width == 0 || height == 0) {
          //rect with area = 0 -> delete it
          rect.destroy();
        } else {
          //predict
          addMaskPrediction(imageId, viewId);
        }
        view_layer.off("pointermove");
        view_layer.off("pointerup");
      }
    }
  }

  //find viewId ancestor for any Konva object
  function findViewId(node) {
    let viewId;
    highlighted_point.getAncestors().forEach((node) => {
      if (node instanceof Konva.Layer) {
        viewId = node.id();
      }
    });
    return viewId;
  }

  //point event handler
  function highlightPoint(hl_point: Konva.Circle, viewId: string) {
    let pointer = findOrCreatePointer(selectedTool.type, viewId);
    pointer.hide();
    highlighted_point = hl_point;
    highlighted_point.radius((1.5 * POINTER_RADIUS) / zoomFactor[viewId]);
    stage.container().style.cursor = "grab";
  }

  function unhighlightPoint(hl_point: Konva.Circle, viewId: string = null) {
    let pointer = findOrCreatePointer(selectedTool.type, viewId);
    pointer.show();
    if (!viewId) {
      viewId = findViewId(hl_point);
    }
    hl_point.radius(POINTER_RADIUS / zoomFactor[viewId]);
    highlighted_point = null;
    stage.container().style.cursor = selectedTool.cursor;
    stage.batchDraw();
  }

  function dragPointEnd(drag_point: Konva.Circle, viewId) {
    stage.container().style.cursor = "grab";
  }

  function dragPointMove(drag_point: Konva.Circle, imageId, viewId) {
    stage.container().style.cursor = "grabbing";

    const view_layer = stage.findOne(`#${viewId}`) as Konva.Layer;
    const img = view_layer.findOne(`#${imageId}`);
    const img_size = img.getSize();
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

    // new prediction on new location
    clearTimeout(timerId); // reinit timer on each move move
    timerId = setTimeout(() => addMaskPrediction(imageId, viewId), 50); // delay before predict to spare CPU
  }

  // Drawing helpers
  function findOrCreatePointer(id: string, viewId: string = null) {
    let pointer: Konva.Circle = stage.findOne(`#${id}`);
    if (!pointer) {
      let zoomF = 1.0; //in some cases we aren't in a view, so we use default scaling
      if (viewId) zoomF = zoomFactor[viewId];
      pointer = new Konva.Circle({
        id: id,
        x: 0,
        y: 0,
        radius: POINTER_RADIUS / zoomF,
        fill: "white",
        strokeWidth: POINTER_STROKEWIDTH / zoomF,
        visible: false,
        listening: false,
        opacity: 0.5,
      });
      toolsLayer.add(pointer);
    }
    return pointer;
  }

  function findOrCreateCrossLines() {
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
        stroke: "red",
        strokeWidth: 1,
        opacity: 0.75,
        dash: [5, 1],
      });
      yLimit = new Konva.Line({
        id: "yline",
        points: [0, 0, stageWidth, 0],
        stroke: "red",
        strokeWidth: 1,
        opacity: 0.75,
        dash: [5, 1],
      });
      crossLineGroup.add(xLimit);
      crossLineGroup.add(yLimit);
      toolsLayer.add(crossLineGroup);
    }
    return { xLimit, yLimit };
  }

  // Pointer tool events
  function displayLabeledPointCreator(tool: LabeledPointTool) {
    if (toolsLayer) {
      //clean other tools
      //TODO: etre générique sur l'ensemble des outils != Point
      let other = toolsLayer.findOne("#crossline");
      if (other) {
        other.destroy();
      }

      let pointer = findOrCreatePointer(tool.type);
      const pointerColor = tool.label === 1 ? "green" : "red";
      pointer.stroke(pointerColor);
      if (!highlighted_point) {
        stage.container().style.cursor = tool.cursor;
      }
    }
  }

  // key events
  function handleKeyDown(event) {
    if (event.key == "Delete" && highlighted_point != null) {
      //get viewId of highlighted_point
      const viewId = findViewId(highlighted_point);
      const to_destroy_hl_point = highlighted_point;
      unhighlightPoint(highlighted_point, viewId);
      //remove Konva Circle
      to_destroy_hl_point.destroy();

      //if existing construct (points, box, ...)
      const view_layer = stage.findOne(`#${viewId}`) as Konva.Layer;
      const input_group = view_layer.findOne("#input") as Konva.Group;
      if (input_group.children.length > 0) {
        //trigger a prediction with existing constructs
        addMaskPrediction(imageId, viewId);
      } else {
        clearCurrentMask(viewId);
      }
    }
    if (event.key == "Escape") {
      for (let view of views) {
        clearInputs(view.viewId);
        clearCurrentMask(view.viewId);
      }
      stage.container().style.cursor = selectedTool.cursor;
      prediction = null;
    }
    if (event.key == "i") {
      console.log("INFOS");
      console.log("masksGT", masksGT);
      console.log("prediction", prediction);
      console.log("stage", stage);
      for (let view of views) {
        const view_layer = stage.findOne(`#${view.viewId}`) as Konva.Layer;
        const MGTgroup: Konva.Group = view_layer.findOne("#masksGT");
        console.log("masksGT Konva group:", MGTgroup);
        console.log("masksGT children length:", MGTgroup.children?.length);
      }
    }
  }

  function displayRectangleCreator(tool: RectangleTool) {
    if (toolsLayer) {
      //clean other tools
      //TODO: etre générique sur l'ensemble des outils != Rectangle
      let pointer: Konva.Circle = stage.findOne(`#${ToolType.LabeledPoint}`);
      if (pointer) pointer.destroy();

      if (!highlighted_point) {
        stage.container().style.cursor = tool.cursor;
      }
    }
  }

  function displayPanMode(tool: PanTool) {
    if (toolsLayer) {
      //clean other tools
      //TODO: etre générique sur l'ensemble des outils != Pan
      let pointer: Konva.Circle = stage.findOne(`#${ToolType.LabeledPoint}`);
      if (pointer) pointer.destroy();
      let crossline = stage.findOne("#crossline");
      if (crossline) crossline.destroy();
      if (!highlighted_point) {
        stage.container().style.cursor = tool.cursor;
      }
    }
  }

  function updateLabeledPointToolState(mousePos: Konva.Vector2d) {
    let pointer = findOrCreatePointer(selectedTool.type);
    const scale = stage.scaleX();
    const pointerScale = Math.max(1, 1 / scale);
    pointer.scaleX(pointerScale);
    pointer.scaleY(pointerScale);
    pointer.x(mousePos.x + 1);
    pointer.y(mousePos.y + 1);
  }

  function updateRectangleToolState(mousePos: Konva.Vector2d) {
    const scale = stage.scaleX();
    const lineScale = Math.max(1, 1 / scale);

    let { xLimit, yLimit } = findOrCreateCrossLines();
    const stageHeight = stage.height();
    xLimit.scaleY(lineScale);
    xLimit.points([mousePos.x, 0, mousePos.x, stageHeight]);
    const stageWidth = stage.width();
    yLimit.scaleX(lineScale);
    yLimit.points([0, mousePos.y, stageWidth, mousePos.y]);
  }
</script>

<div class="h-full w-full relative bg-zinc-100" bind:this={stageContainer}>
  <Stage
    bind:config={stageConfig}
    bind:handle={stage}
    on:mousemove={handleMouseMoveStage}
    on:mouseenter={handleMouseEnterStage}
    on:mouseleave={handleMouseLeaveStage}
  >
    {#each views as view}
      {#if images[view.viewId]}
        <Layer
          config={{ id: view.viewId }}
          on:wheel={(event) => handleWheelOnImage(event, view.viewId)}
        >
          <KonvaImage
            config={{ image: images[view.viewId], id: imageId }}
            on:pointerdown={(event) =>
              handleClickOnImage(event, imageId, view.viewId)}
            on:pointerup={(event) => handlePointerUpOnImage(event, view.viewId)}
            on:dblclick={(event) => handleDblClickOnImage(event, view.viewId)}
          />
          <Group config={{ id: "masks" }} />
          <Group config={{ id: "masksGT" }} />
          <Group config={{ id: "bboxes" }} />
          <Group config={{ id: "input" }} />
        </Layer>
      {/if}
    {/each}
    <Layer config={{ name: "tools" }} bind:handle={toolsLayer} />
  </Stage>
</div>
<svelte:window on:keydown={handleKeyDown} />
