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
  } from "./tools";
  import type {
    LabeledClick,
    Box,
    InteractiveImageSegmenterOutput,
  } from "@pixano/models";
  import type { Mask, BBox, ViewData } from "./interfaces";

  // Exports
  export let embeddings = {};
  export let itemId: string;
  export let views: Array<ViewData>;
  export let masks: Array<Mask> | null;
  export let bboxes: Array<BBox> = null;
  export let selectedTool: Tool | null;
  export let categoryColor = null;
  export let prediction: InteractiveImageSegmenterOutput = null;

  const POINTER_RADIUS: number = 6;
  const POINTER_STROKEWIDTH: number = 3;
  const RECT_STROKEWIDTH: number = 1.5;
  const MASK_STROKEWIDTH: number = 1.0;
  const short = shortid;

  let inferenceModelWarning = false;
  let embeddingDirectoryWarning = false;

  let zoomFactor = {}; //dict of zoomFactors by viewId {viewId: zoomFactor}
  let timerId;

  // References to HTML Elements
  let stageContainer: HTMLElement;
  let images: Record<string, HTMLImageElement> = {}; //dict {viewId: HTMLImageElement}

  // References to Konva Elements
  let stage: Konva.Stage;
  let toolsLayer: Konva.Layer;
  // let imageKonva: Konva.Image;
  let highlighted_point: Konva.Circle = null;

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

  // ********** WARNINGS ********** //

  function toggleInferenceModelModal() {
    inferenceModelWarning = !inferenceModelWarning;
  }

  function toggleEmbeddingDirectoryModal() {
    embeddingDirectoryWarning = !embeddingDirectoryWarning;
  }

  // ********** INIT ********** //

  onMount(() => {
    //console.log(`selected tool ${selectedTool?.type}`);

    // Load Image(s)
    for (let view of views) {
      zoomFactor[view.viewId] = 1;
      const image = new Image();
      image.src = view.imageURL;
      image.onload = (event) => {
        onLoadViewImage(event, view.viewId).then(() => {
          scaleView(view);
          //hack to refresh view (display masks/bboxes)
          masks = masks;
        });
      };
    }
    prev_views = views;

    // Calculate new grid size
    gridSize.cols = Math.ceil(Math.sqrt(views.length));
    gridSize.rows = Math.ceil(views.length / gridSize.cols);

    // Fire stage events observers
    resizeObserver.observe(stageContainer);
  });

  afterUpdate(() => {
    if (selectedTool) {
      handleChangeTool();
    } else {
      // reset
      stage.container().style.cursor = "default";
    }
    if (prediction && prediction.validated) {
      validateCurrentMask(prediction.viewId);
    }
    if (masks) {
      for (let view of views) addMasks(view.viewId, itemId);
    }
    if (bboxes) {
      for (let view of views) addBboxes(view.viewId, itemId);
    }

    if (views !== prev_views) {
      // Load Image(s)
      clearAnnotationAndInputs();
      for (let view of views) {
        const viewLayer = stage.findOne(`#${view.viewId}`) as Konva.Layer;
        zoomFactor[view.viewId] = 1;
        const image = new Image();
        image.src = view.imageURL;
        image.onload = (event) => {
          onLoadViewImage(event, view.viewId).then(() => {
            const konvaImg = viewLayer.findOne(`#${itemId}`) as Konva.Image;
            konvaImg.image(image);
            scaleView(view);
            //hack to refresh view (display masks/bboxes)
            masks = masks;
          });
        };
      }
      prev_views = views;
    }
  });

  async function onLoadViewImage(event, viewId: string) {
    images[viewId] = event.target;
  }

  function scaleView(view: ViewData) {
    const viewLayer = stage.findOne(`#${view.viewId}`) as Konva.Layer;
    if (viewLayer) {
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

      viewLayer.scale({ x: scale, y: scale });

      // Center view
      let offsetX =
        (maxWidth - images[view.viewId].width * scale) / 2 +
        grid_pos.x * maxWidth;
      let offsetY =
        (maxHeight - images[view.viewId].height * scale) / 2 +
        grid_pos.y * maxHeight;
      viewLayer.x(offsetX);
      viewLayer.y(offsetY);
    } else {
      console.log("   CANNOT scale");
    }
  }

  function findViewId(node) {
    let viewId;
    highlighted_point.getAncestors().forEach((node) => {
      if (node instanceof Konva.Layer) {
        viewId = node.id();
      }
    });
    return viewId;
  }

  // ********** BOUNDING BOXES AND MASKS ********** //

  function addBboxes(viewId, itemId) {
    const viewLayer: Konva.Layer = stage.findOne(`#${viewId}`);

    if (viewLayer) {
      const bboxesGroup: Konva.Group = viewLayer.findOne("#bboxes");
      const image: Konva.Image = viewLayer.findOne(`#${itemId}`);

      const listBboxIds = [];
      for (let i = 0; i < bboxes.length; ++i) {
        if (bboxes[i].viewId === viewId) {
          listBboxIds.push(bboxes[i].id);

          //don't add a bbox that already exist
          let bbox = bboxesGroup.findOne(`#${bboxes[i].id}`);
          if (!bbox) {
            addBBox(
              bboxes[i],
              image,
              categoryColor(bboxes[i].catId),
              bboxesGroup
            );
          } else {
            //apply visibility
            bbox.visible(bboxes[i].visible);
          }
        }
      }

      //remove bbox that's no longer exist in bboxes
      const list_to_destroy = []; //need to build a list to not destroy while looping children
      for (let bbox of bboxesGroup.children) {
        if (!listBboxIds.includes(bbox.id())) list_to_destroy.push(bbox);
      }
      for (let bbox of list_to_destroy) bbox.destroy();
    }
  }

  function addBBox(
    bbox: BBox,
    image: Konva.Image,
    color: any,
    bboxesGroup: Konva.Group
  ) {
    const img_w = (image.image() as HTMLImageElement).naturalWidth;
    const img_h = (image.image() as HTMLImageElement).naturalHeight;
    const rect_x = image.x() + bbox.bbox[0] * img_w;
    const rect_y = image.y() + bbox.bbox[1] * img_h;
    const rect_width = bbox.bbox[2] * img_w;
    const rect_height = bbox.bbox[3] * img_h;

    const bboxGroup = new Konva.Group({
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
    bboxGroup.add(kbbox);

    // Create a label object
    const label = new Konva.Label({
      x: rect_x + 1,
      y: rect_y + 1,
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
        fontFamily: "poppins",
        padding: 0,
        x: rect_x + 1,
        y: rect_y + 1,
      })
    );

    // Add the label to the group
    bboxGroup.add(label);
    bboxesGroup.add(bboxGroup);
  }

  function addMasks(viewId, itemId) {
    const viewLayer: Konva.Layer = stage.findOne(`#${viewId}`);

    if (viewLayer) {
      const masksGroup: Konva.Group = viewLayer.findOne("#masks");
      const image = viewLayer.findOne(`#${itemId}`);

      let maskIds = [];
      for (let i = 0; i < masks.length; ++i) {
        maskIds.push(masks[i].id);
        if (masks[i].viewId === viewId) {
          //don't add a mask that already exist
          let mask = masksGroup.findOne(`#${masks[i].id}`);
          if (!mask) {
            addMask(
              masks[i].mask,
              masks[i].id,
              image.x(),
              image.y(),
              image.scale(),
              categoryColor(masks[i].catId),
              masks[i].visible,
              1.0,
              masksGroup
            );
          } else {
            //update visibility & opacity
            mask.visible(masks[i].visible);
            mask.opacity(masks[i].opacity);
            //update color
            let shape = mask as Konva.Shape;
            if (typeof shape.fill === "function") {
              var pred = new Option().style;
              pred.color = categoryColor(masks[i].catId);
              shape.fill(
                `rgba(${pred.color.replace("rgb(", "").replace(")", "")}, 0.35)`
              );
              shape.stroke(pred.color);
            }
          }
        }
      }

      //remove masks that no longer exists
      const list_to_destroy = []; //need to build a list to not destroy while looping children
      for (let mask of masksGroup.children) {
        if (!maskIds.includes(mask.id())) list_to_destroy.push(mask);
      }
      for (let mask of list_to_destroy) mask.destroy();
    }
  }

  function addMask(
    masksSVG: Array<string>,
    id: string,
    x: number,
    y: number,
    scale: Konva.Vector2d,
    stroke: string,
    visibility: boolean,
    opacity: number,
    masksGroup: Konva.Group
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
      strokeWidth: MASK_STROKEWIDTH,
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
    masksGroup.add(mask);
  }

  // ********** CURRENT ANNOTATION ********** //

  async function updateCurrentMask(itemId, viewId) {
    const points = getInputPoints(viewId);
    const box = getInputRect(viewId);
    const input = {
      image: images[viewId],
      embedding: viewId in embeddings ? embeddings[viewId] : null,
      points: points,
      box: box,
    };

    if (selectedTool.postProcessor == null) {
      toggleInferenceModelModal();
      clearAnnotationAndInputs();
    } else if (
      !(viewId in embeddings) ||
      (viewId in embeddings && embeddings[viewId] == null)
    ) {
      toggleEmbeddingDirectoryModal();
      clearAnnotationAndInputs();
    } else {
      const results = await selectedTool.postProcessor.segmentImage(input);
      if (results) {
        const currentMaskGroup = findOrCreateCurrentMask(viewId);
        const viewLayer = stage.findOne(`#${viewId}`) as Konva.Layer;
        const image = viewLayer.findOne(`#${itemId}`);

        // always clean existing masks before adding a new prediction
        currentMaskGroup.removeChildren();

        const new_id = short.generate();
        prediction = {
          id: new_id,
          viewId: viewId,
          label: "",
          catId: -1,
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
          currentMaskGroup
        );
      }
    }
  }

  function findOrCreateCurrentMask(viewId): Konva.Group {
    const viewLayer = stage.findOne(`#${viewId}`) as Konva.Layer;

    let currentAnnGroup: Konva.Group = viewLayer.findOne("#currentAnnotation");

    // Get and update the current annotation masks
    let currentMaskGroup = currentAnnGroup.findOne(
      "#currentMask"
    ) as Konva.Group;

    if (!currentMaskGroup) {
      currentMaskGroup = new Konva.Group({
        id: "currentMask",
      });
      currentAnnGroup.add(currentMaskGroup);
    }
    return currentMaskGroup;
  }

  function clearCurrentAnnotation(viewId) {
    const viewLayer = stage.findOne(`#${viewId}`) as Konva.Layer;
    let currentAnnGroup: Konva.Group = viewLayer.findOne("#currentAnnotation");
    let currentMaskGroup = currentAnnGroup.findOne(
      "#currentMask"
    ) as Konva.Group;
    if (currentMaskGroup) currentMaskGroup.destroy();
    if (selectedTool.postProcessor) selectedTool.postProcessor.reset();
  }

  function validateCurrentMask(viewId) {
    if (prediction.validated) {
      const viewLayer = stage.findOne(`#${viewId}`) as Konva.Layer;
      let currentMaskGroup = findOrCreateCurrentMask(viewId);
      if (currentMaskGroup) {
        //move currentMaskGroup to masksGroup
        const masksGroup: Konva.Group = viewLayer.findOne("#masks");
        currentMaskGroup.id(prediction.id);
        // change color
        for (let s of currentMaskGroup.children) {
          let shape = s as Konva.Shape;
          var pred = new Option().style;
          pred.color = categoryColor(prediction.catId);
          shape.fill(
            `rgba(${pred.color.replace("rgb(", "").replace(")", "")}, 0.35)`
          );
          shape.stroke(pred.color);
        }
        currentMaskGroup.moveTo(masksGroup);
        masks.push({
          viewId: viewId,
          id: prediction.id,
          mask: prediction.output.masksImageSVG,
          rle: prediction.output.rle,
          catId: prediction.catId,
          visible: true,
          opacity: 1.0,
        });

        if (highlighted_point) unhighlightInputPoint(highlighted_point);
        clearInputs(prediction.viewId);
        prediction = null;
      }
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
      default:
        // Reset or disable any specific behavior
        break;
    }
  }

  function scaleInputs(viewId) {
    //keep points/box at constant scale
    const viewLayer = stage.findOne(`#${viewId}`) as Konva.Layer;
    const inputGroup = viewLayer.findOne("#input") as Konva.Group;
    for (let pt of inputGroup.children) {
      if (pt instanceof Konva.Circle) {
        pt.radius(POINTER_RADIUS / zoomFactor[viewId]);
        pt.strokeWidth(POINTER_STROKEWIDTH / zoomFactor[viewId]);
      }
      if (pt instanceof Konva.Rect) {
        pt.strokeWidth(RECT_STROKEWIDTH / zoomFactor[viewId]);
      }
    }
  }

  function clearInputs(viewId) {
    const viewLayer = stage.findOne(`#${viewId}`) as Konva.Layer;
    const inputGroup = viewLayer.findOne("#input") as Konva.Group;
    inputGroup.destroyChildren();
  }

  // ********** PAN TOOL ********** //

  function displayPanTool(tool: PanTool) {
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
      // deactivate drag on input points
      toggleInputPointDrag(false);
    }
  }

  // ********** INPUT POINTS TOOL ********** //

  function displayInputPointTool(tool: LabeledPointTool) {
    if (toolsLayer) {
      //clean other tools
      //TODO: etre générique sur l'ensemble des outils != Point
      let crossline = toolsLayer.findOne("#crossline");
      if (crossline) crossline.destroy();

      let pointer = findOrCreateInputPointPointer(tool.type);
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
    let pointer = findOrCreateInputPointPointer(selectedTool.type);
    const scale = stage.scaleX();
    const pointerScale = Math.max(1, 1 / scale);
    pointer.scaleX(pointerScale);
    pointer.scaleY(pointerScale);
    pointer.x(mousePos.x + 1);
    pointer.y(mousePos.y + 1);
  }

  function findOrCreateInputPointPointer(id: string, viewId: string = null) {
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

  function getInputPoints(viewId): Array<LabeledClick> {
    //get points as Array<LabeledClick>
    let points: Array<LabeledClick> = [];
    const viewLayer = stage.findOne(`#${viewId}`) as Konva.Layer;
    let inputGroup: Konva.Group = viewLayer.findOne("#input");
    for (let pt of inputGroup.children) {
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

  function toggleInputPointDrag(toggle: boolean) {
    const input_groups = stage.find("#input");
    for (let input_group of input_groups) {
      for (let node of (input_group as Konva.Group).children) {
        if (node instanceof Konva.Circle) {
          node.listening(toggle);
        }
      }
    }
  }

  function dragInputPointEnd(drag_point: Konva.Circle, viewId) {
    stage.container().style.cursor = "grab";
  }

  function dragInputPointMove(drag_point: Konva.Circle, itemId, viewId) {
    stage.container().style.cursor = "grabbing";

    const viewLayer = stage.findOne(`#${viewId}`) as Konva.Layer;
    const image = viewLayer.findOne(`#${itemId}`);
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

    // new prediction on new location
    clearTimeout(timerId); // reinit timer on each move move
    timerId = setTimeout(() => updateCurrentMask(itemId, viewId), 50); // delay before predict to spare CPU
  }

  function highlightInputPoint(hl_point: Konva.Circle, viewId: string) {
    let pointer = findOrCreateInputPointPointer(selectedTool.type, viewId);
    pointer.hide();
    highlighted_point = hl_point;
    highlighted_point.radius((1.5 * POINTER_RADIUS) / zoomFactor[viewId]);
    stage.container().style.cursor = "grab";
  }

  function unhighlightInputPoint(
    hl_point: Konva.Circle,
    viewId: string = null
  ) {
    let pointer = findOrCreateInputPointPointer(selectedTool.type, viewId);
    pointer.show();
    if (!viewId) {
      viewId = findViewId(hl_point);
    }
    hl_point.radius(POINTER_RADIUS / zoomFactor[viewId]);
    highlighted_point = null;
    stage.container().style.cursor = selectedTool.cursor;
    stage.batchDraw();
  }

  // ********** INPUT RECTANGLE TOOL ********** //

  function displayInputRectTool(tool: RectangleTool) {
    if (toolsLayer) {
      //clean other tools
      //TODO: etre générique sur l'ensemble des outils != Rectangle
      let pointer: Konva.Circle = stage.findOne(`#${ToolType.LabeledPoint}`);
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

    let { xLimit, yLimit } = findOrCreateInputRectPointer();
    const stageHeight = stage.height();
    xLimit.scaleY(lineScale);
    xLimit.points([mousePos.x, 0, mousePos.x, stageHeight]);
    const stageWidth = stage.width();
    yLimit.scaleX(lineScale);
    yLimit.points([0, mousePos.y, stageWidth, mousePos.y]);
  }

  function findOrCreateInputRectPointer() {
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
    return { xLimit, yLimit };
  }

  function getInputRect(viewId): Box {
    //get box as Box
    let box: Box = null;
    const viewLayer = stage.findOne(`#${viewId}`) as Konva.Layer;
    let inputGroup: Konva.Group = viewLayer.findOne("#input");
    for (let rect of inputGroup.children) {
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

  function dragInputRectMove(viewId: string) {
    if (selectedTool?.type == ToolType.Rectangle) {
      const viewLayer = stage.findOne(`#${viewId}`) as Konva.Layer;
      const inputGroup = viewLayer.findOne("#input") as Konva.Group;
      const rect = inputGroup.findOne("#drag-rect") as Konva.Rect;
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

  function dragInputRectEnd(viewId: string): void {
    if (selectedTool?.type == ToolType.Rectangle) {
      const viewLayer = stage.findOne(`#${viewId}`) as Konva.Layer;
      const inputGroup = viewLayer.findOne("#input") as Konva.Group;
      const rect = inputGroup.findOne("#drag-rect") as Konva.Rect;
      if (rect) {
        const { width, height } = rect.size();
        if (width == 0 || height == 0) {
          //rect with area = 0 -> delete it
          rect.destroy();
        } else {
          //predict
          updateCurrentMask(itemId, viewId);
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
      let pointer: Konva.Circle = stage.findOne(`#${ToolType.LabeledPoint}`);
      if (pointer) pointer.destroy();
      let crossline = stage.findOne("#crossline");
      if (crossline) crossline.destroy();

      if (!highlighted_point) {
        stage.container().style.cursor = tool.cursor;
      }
      // deactivate drag on input points
      toggleInputPointDrag(false);
    }
  }

  function clearAnnotationAndInputs() {
    for (let view of views) {
      clearInputs(view.viewId);
      clearCurrentAnnotation(view.viewId);
    }
    stage.container().style.cursor = selectedTool.cursor;
    prediction = null;
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

  function handleDragEndOnView(viewId: string) {
    const viewLayer = stage.findOne(`#${viewId}`);
    viewLayer.draggable(false);
    viewLayer.off("dragend dragmove");
  }

  function handlePointerUpOnImage(event, viewId: string) {
    const viewLayer = stage.findOne(`#${viewId}`);
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

  function handleDoubleClickOnImage(event, viewId: string) {
    // put double-clickd view on top of views
    const viewLayer = stage.findOne(`#${viewId}`) as Konva.Layer;
    viewLayer.moveToTop();
    //keeps tools on top
    toolsLayer.moveToTop();
  }

  async function handleClickOnImage(event, itemId: string, viewId: string) {
    const viewLayer = stage.findOne(`#${viewId}`) as Konva.Layer;
    // Perfome tool action if any active tool
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
        highlightInputPoint(event.target as Konva.Circle, viewId)
      );
      input_point.on("pointerout", (event) =>
        unhighlightInputPoint(event.target as Konva.Circle, viewId)
      );
      input_point.on("dragmove", (event) =>
        dragInputPointMove(event.target as Konva.Circle, itemId, viewId)
      );
      input_point.on("dragend", (event) =>
        dragInputPointEnd(event.target as Konva.Circle, viewId)
      );
      const inputGroup = viewLayer.findOne("#input") as Konva.Group;
      inputGroup.add(input_point);
      highlightInputPoint(input_point, viewId);

      updateCurrentMask(itemId, viewId);
    } else if (selectedTool?.type == ToolType.Rectangle) {
      const pos = viewLayer.getRelativePointerPosition();
      const inputGroup = viewLayer.findOne("#input") as Konva.Group;

      //add RECT
      let rect = inputGroup.findOne("#drag-rect") as Konva.Rect;
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
        inputGroup.add(rect);
      }
      viewLayer.on("pointermove", () => dragInputRectMove(viewId));
      viewLayer.on("pointerup", () => dragInputRectEnd(viewId));
    }
  }

  function zoom(stage: Konva.Stage, direction, viewId): number {
    // Defines zoom speed
    const zoomScale = 1.05;

    const viewLayer = stage.findOne(`#${viewId}`) as Konva.Layer;

    // Get old scaling
    const oldScale = viewLayer.scaleX();

    // Get mouse position
    const pointer = stage.getRelativePointerPosition();
    const mousePointTo = {
      x: (pointer.x - viewLayer.x()) / oldScale,
      y: (pointer.y - viewLayer.y()) / oldScale,
    };

    // Calculate new scaling
    const newScale =
      direction > 0 ? oldScale * zoomScale : oldScale / zoomScale;

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
      highlightInputPoint(highlighted_point, viewId);
    }
  }

  // ********** KEY EVENTS ********** //

  function handleKeyDown(event) {
    if (event.key == "Delete" && highlighted_point != null) {
      //get viewId of highlighted_point
      const viewId = findViewId(highlighted_point);
      const to_destroy_hl_point = highlighted_point;
      unhighlightInputPoint(highlighted_point, viewId);
      //remove Konva Circle
      to_destroy_hl_point.destroy();

      //if existing construct (points, box, ...)
      const viewLayer = stage.findOne(`#${viewId}`) as Konva.Layer;
      const inputGroup = viewLayer.findOne("#input") as Konva.Group;
      if (inputGroup.children.length > 0) {
        //trigger a prediction with existing constructs
        updateCurrentMask(itemId, viewId);
      } else {
        clearCurrentAnnotation(viewId);
      }
    }
    if (event.key == "Escape") {
      clearAnnotationAndInputs();
    }
    if (event.key == "i") {
      console.log("INFOS");
      console.log("masks", masks);
      console.log("prediction", prediction);
      console.log("stage", stage);
      for (let view of views) {
        const viewLayer = stage.findOne(`#${view.viewId}`) as Konva.Layer;
        const masksGroup: Konva.Group = viewLayer.findOne("#masks");
        console.log("masks Konva group:", masksGroup);
        console.log("masks children length:", masksGroup.children?.length);
      }
    }
  }
</script>

<div
  class="h-full w-full relative bg-zinc-100 dark:bg-zinc-900"
  bind:this={stageContainer}
>
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
            config={{ image: images[view.viewId], id: itemId }}
            on:pointerdown={(event) =>
              handleClickOnImage(event, itemId, view.viewId)}
            on:pointerup={(event) => handlePointerUpOnImage(event, view.viewId)}
            on:dblclick={(event) =>
              handleDoubleClickOnImage(event, view.viewId)}
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
{#if inferenceModelWarning}
  <WarningModal
    message="No interactive model set up, cannot segment."
    details="Please refer to our interactive annotation notebook for information on how to export your model to ONNX."
    on:confirm={toggleInferenceModelModal}
  />
{/if}
{#if embeddingDirectoryWarning}
  <WarningModal
    message="No embedding directory found, cannot segment."
    details="Please refer to our interactive annotation notebook for information on how to precompute embeddings on your dataset."
    on:confirm={toggleEmbeddingDirectoryModal}
  />
{/if}
<svelte:window on:keydown={handleKeyDown} />
