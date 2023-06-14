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

    import { ToolType } from "./tools";
    import type { Tool, LabeledPointTool, RectangleTool } from "./tools";
    import type {
        LabeledClick,
        Box,
        InteractiveImageSegmenterOutput,
    } from "../../models/src/interactive_image_segmentation";
    import type { MaskGT } from "../../../apps/annotator/src/lib/interfaces";

    const POINTER_RADIUS: number = 6;
    const POINTER_STROKEWIDTH: number = 3;
    const RECT_STROKEWIDTH: number = 1.5;
    let zoomFactor: number = 1;
    let timerId;

    // Inputs
    export let imageURL: string;
    export let embedding: any = null;
    export let imageId: string;
    export let viewId: string;

    export let masksGT: Array<MaskGT>;

    let prevImg: string = "";
    //export let imageEmbedding = null;
    export let selectedTool: Tool | null;

    // Output
    export let prediction: InteractiveImageSegmenterOutput;

    // References to HTML Elements
    let stageContainer: HTMLElement;
    let image: HTMLImageElement;

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

    // Init
    onMount(() => {
        //console.log(`selected tool ${selectedTool?.type}`);

        // Load Image
        const img = new Image();
        img.src = imageURL;
        img.onload = () => {
            image = img;
            
            const layerView = stage.findOne(`#${viewId}`) as Konva.Layer;

            // Fit stage
            let scaleByHeight = stage.height() / image.height;
            let scaleByWidth = stage.width() / image.width;
            let scale = Math.min(scaleByWidth, scaleByHeight);

            layerView.scale({x: scale, y: scale});

            // Center stage
            let offsetX = (stage.width() - (image.width) * scale) / 2;
            let offsetY = (stage.height() - (image.height) * scale) / 2;
            layerView.x(offsetX);
            layerView.y(offsetY);
        };

        // Fire stage events observers
        resizeObserver.observe(stageContainer);
    });

    function resetStage() {
        let input = stage.findOne("#input") as Konva.Group;
        let masks = stage.findOne("#masks") as Konva.Group;

        input.destroyChildren();
        masks.destroyChildren();
    }

    afterUpdate(() => {
        if (selectedTool) {
            handleToolChange();
        } else {
            // reset
            stage.container().style.cursor = "default";
        }
        if (prediction && prediction.validated) {
            handleMaskValidated(prediction.view);
        }
        if (masksGT) {
            addMaskGT(viewId, imageId);
        }

        // if (imageURL !== prevImg) {
        //     let img = new Image();
        //     img.onload = function () {
        //         resetStage();
        //         const konvaImg = stage.findOne("#image") as Konva.Image;
        //         konvaImg.image(img);
        //         imageURL = prevImg;
        //     };
        //     img.src = imageURL;
        // }

    });

    function getBox(viewId): Box {
        //get box as Box
        let box: Box = null;
        const view = stage.findOne(`#${viewId}`) as Konva.Layer;
        let input_group: Konva.Group = view.findOne("#input");
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
        const view = stage.findOne(`#${viewId}`) as Konva.Layer;
        let input_group: Konva.Group = view.findOne("#input");
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
        const view = stage.findOne(`#${viewId}`) as Konva.Layer;
        const input_group = view.findOne("#input") as Konva.Group;
        input_group.destroyChildren();
    }

    function clearCurrentMask(viewId) {
        const view = stage.findOne(`#${viewId}`) as Konva.Layer;
        let masks: Konva.Group = view.findOne("#masks");
        let predictedMasks = masks.findOne("#predictedMasks") as Konva.Group;
        if (predictedMasks) predictedMasks.destroy();
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
                fill = "rgba(255, 255, 255, 0.25)";
                break;
        }
        //utility functions to extract coords from SVG
        //works only with SVG format "Mx0 y0 Lx1 y1 ... xn yn"
        // --> format generated by convertSegmentsToSVG
        function m_part(svg: string) {
            const splits = svg.split(" ");
            const x = splits[0].slice(1); //remove "M"
            return {x: parseInt(x), y: parseInt(splits[1])}
        }
        function l_part(svg: string) {
            const splits = svg.split(" ");
            const x0 = splits[2].slice(1); //remove "L"
            const res = [{x: parseInt(x0), y: parseInt(splits[3])}]
            for (let i=4; i < splits.length; i+=2) {
                res.push({
                    x: parseInt(splits[i]),
                    y: parseInt(splits[i+1])
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
            }
        });
        group.add(mask);
    }

    function findOrCreatePredictedMaskGroup(viewId): Konva.Group {
        const view = stage.findOne(`#${viewId}`) as Konva.Layer;

        // findOrCreate mask group;
        let masks: Konva.Group = view.findOne("#masks");

        // Get and update the current predicted masks
        let predictedMasksGroup = masks.findOne(
            "#predictedMasks"
        ) as Konva.Group;

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
            image: image,
            embedding: embedding,
            points: points,
            box: box,
        };

        if(selectedTool.postProcessor == null) {
            console.log("No segmentation model connected, cannot segment")
        } else {
            const results = await selectedTool.postProcessor.segmentImage(input);
            if (results) {
                const group = findOrCreatePredictedMaskGroup(viewId);
                const image = stage.findOne(`#${imageId}`);
                
                // always clean existing masks before adding a new prediction
                group.removeChildren();
                const new_id = Math.floor(Math.random() * 5000).toString(); //TODO use shortuiid instead
                prediction = {
                    id: new_id,
                    view: viewId,
                    shape: results.masksImage,
                    input_points: points,
                    input_box: box,
                    validated: false,
                };
                addMask(results.masksImage, new_id, image.x(), image.y(), image.scale(), "green", true, group);
            }
        }
    }

    function addMaskGT(viewId, imageId) {
        const view: Konva.Layer = stage.findOne(`#${viewId}`);

        if (view) {
            const group: Konva.Group = view.findOne("#masksGT");
            const image = stage.findOne(`#${imageId}`);

            const listMaskGTIds = []
            for (let i = 0; i < masksGT.length; ++i) {
                listMaskGTIds.push(masksGT[i].id);

                //don't add a mask that already exist
                let mask = group.findOne(`#${masksGT[i].id}`);
                if (!mask) {
                    addMask(masksGT[i].mask, masksGT[i].id, image.x(), image.y(), image.scale(), "blue", masksGT[i].visible, group);
                } else {
                    //apply visibility
                    mask.visible(masksGT[i].visible);
                }
            }

            //remove masks that's no longer exist in masksGT
            for (let mask of group.children) {
                if (!(listMaskGTIds.includes(mask.id()))) {
                    mask.destroy();
                }
            }

        }
    }

    // Events Handlers
    function handleMaskValidated(viewId) {
        if(prediction.validated) {
            const view = stage.findOne(`#${viewId}`) as Konva.Layer;
            let predictedMasks = findOrCreatePredictedMaskGroup(viewId);
            if (predictedMasks) {
                //move predictedMasks to maskGT
                const masksGT_group: Konva.Group = view.findOne("#masksGT");
                predictedMasks.id(prediction.id);
                // change color  //TODO: use table of color by class or whatever
                for(let s of predictedMasks.children) {
                    let shape = s as Konva.Shape;
                    shape.fill("rgba(0, 0, 255, 0.25)")
                    shape.stroke("blue")
                }
                predictedMasks.moveTo(masksGT_group);
                masksGT.push({
                    id: prediction.id,
                    mask: prediction.shape,
                    rle: null,  //prediction.rle,
                    visible: true
                })

                clearInputs(prediction.view);
                prediction = null;
            }
        }
    }

    function handleToolChange() {
        // Update the behavior of the canvas stage based on the selected tool
        // You can add more cases for different tools as needed
        switch (selectedTool.type) {
            case ToolType.LabeledPoint:
                displayLabeledPointCreator(selectedTool as LabeledPointTool);
                break;
            case ToolType.Rectangle:
                displayRectangleCreator();
                // Enable box creation or change cursor style
                break;
            case ToolType.Pan:
                displayPanMode();
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
        const view = stage.findOne(`#${viewId}`);
        view.draggable(false);
        view.off("dragend dragmove");
    }

    function handlePointerUpOnImage(event, viewId: string) {
        const view = stage.findOne(`#${viewId}`);
        view.draggable(false);
        view.off("dragend dragmove");
    }

    async function handleClickOnImage(event, imageId: string, viewId: string) {
        const view = stage.findOne(`#${viewId}`) as Konva.Layer;

        // Perfome tool action if any active tool
        if (selectedTool?.type == ToolType.Pan) {
            view.draggable(true);
            view.on("dragmove", handleDragMoveOnView);
            view.on("dragend", () => handleDragEndOnView(viewId));
        } else if (selectedTool?.type == ToolType.LabeledPoint) {
            const clickOnViewPos = view.getRelativePointerPosition();

            //add Konva Point
            const input_point = new Konva.Circle({
                name: `${(selectedTool as LabeledPointTool).label}`,
                x: clickOnViewPos.x,
                y: clickOnViewPos.y,
                radius: POINTER_RADIUS / zoomFactor,
                stroke: "white",
                fill:
                    (selectedTool as LabeledPointTool).label === 1
                        ? "green"
                        : "red",
                strokeWidth: POINTER_STROKEWIDTH / zoomFactor,
                visible: true,
                listening: true,
                opacity: 0.75,
                draggable: true,
            });
            input_point.on("pointerenter", (event) =>
                highlightPoint(event.target as Konva.Circle)
            );
            input_point.on("pointerout", (event) =>
                unhighlightPoint(event.target as Konva.Circle)
            );
            input_point.on("dragmove", (event) =>
                dragPointMove(event.target as Konva.Circle, imageId, viewId)
            );
            input_point.on("dragend", (event) =>
                dragPointEnd(event.target as Konva.Circle, viewId)
            );
            const input_group = stage.findOne("#input") as Konva.Group;
            input_group.add(input_point);
            highlightPoint(input_point);

            addMaskPrediction(imageId, viewId);

        } else if (selectedTool?.type == ToolType.Rectangle) {
            const pos = view.getRelativePointerPosition();
            const input_group = view.findOne("#input") as Konva.Group;

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
                    strokeWidth: RECT_STROKEWIDTH / zoomFactor,
                    listening: false,
                });
                input_group.add(rect);
            }
            view.on("pointermove", () => handleToolBoxDragMove(viewId));
            view.on("pointerup", () => handleToolBoxDragEnd(viewId));
        }
    }

    function handleToolBoxDragMove(viewId: string) {
        if (selectedTool?.type == ToolType.Rectangle) {
            const view = stage.findOne(`#${viewId}`) as Konva.Layer;
            const input_group = view.findOne("#input") as Konva.Group;
            const rect = input_group.findOne("#drag-rect") as Konva.Rect;
            if (rect) {
                const pos = view.getRelativePointerPosition();
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
            const view = stage.findOne(`#${viewId}`) as Konva.Layer;
            const input_group = view.findOne("#input") as Konva.Group;
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
                view.off("pointermove");
                view.off("pointerup");
            }
        }
    }

    //point event handler
    function highlightPoint(hl_point: Konva.Circle) {
        let pointer = findOrCreatePointer(selectedTool.type);
        pointer.hide();
        highlighted_point = hl_point;
        highlighted_point.radius((1.5 * POINTER_RADIUS) / zoomFactor);
        stage.container().style.cursor = "grab";
    }

    function unhighlightPoint(hl_point: Konva.Circle) {
        let pointer = findOrCreatePointer(selectedTool.type);
        pointer.show();
        const unhighlight_point = hl_point;
        unhighlight_point.radius(POINTER_RADIUS / zoomFactor);
        highlighted_point = null;
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

        ;
    }

    // Drawing helpers
    function findOrCreatePointer(id: string) {
        let pointer: Konva.Circle = stage.findOne(`#${id}`);
        if (!pointer) {
            pointer = new Konva.Circle({
                id: id,
                x: 0,
                y: 0,
                radius: POINTER_RADIUS,
                fill: "white",
                strokeWidth: POINTER_STROKEWIDTH,
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
            let other = stage.findOne("#crossline");
            if (other) {
                other.destroy();
            }

            let pointer = findOrCreatePointer(tool.type);
            const pointerColor = tool.label === 1 ? "green" : "red";
            pointer.stroke(pointerColor);
            if (!highlighted_point) {
                stage.container().style.cursor = "crosshair";
            }
        }
    }

    // key events
    function handleKeyDown(event) {
        if (event.key == "Delete" && highlighted_point != null) {
            //get viewId of highlighted_point
            let viewId;
            highlighted_point.getAncestors().forEach((node) => {
                if (node instanceof Konva.Layer) {
                    viewId = node.id();
                }
            });

            //remove Konva Circle
            highlighted_point.destroy();
            highlighted_point = null;

            //if existing construct (points, box, ...)
            const view = stage.findOne(`#${viewId}`) as Konva.Layer;
            const input_group = view.findOne("#input") as Konva.Group;
            if (input_group.children.length > 0) {
                //trigger a prediction with existing constructs
                addMaskPrediction(imageId, viewId);
            } else {
                clearCurrentMask(viewId);
            }
        }
        if (event.key == "Escape") {
            clearInputs(viewId);
            clearCurrentMask(viewId);
            prediction = null;
        }
        if (event.key == "i") {
            console.log("INFOS")
            console.log("masksGT", masksGT);
            console.log("prediction", prediction);
            console.log("stage", stage);
            const view = stage.findOne(`#${viewId}`) as Konva.Layer;
            const MGTgroup: Konva.Group = view.findOne("#masksGT");
            console.log("masksGT Konva group:", MGTgroup);
            console.log("masksGT children length:", MGTgroup.children?.length);

        }
    }

    function displayRectangleCreator() {
        if (toolsLayer) {
            //clean other tools
            //TODO: etre générique sur l'ensemble des outils != Rectangle
            let pointer: Konva.Circle = stage.findOne(`#${ToolType.LabeledPoint}`);
            if (pointer) pointer.destroy();

            if (!highlighted_point) {
                stage.container().style.cursor = "crosshair";
            }
        }
    }

    function displayPanMode() {
        if (toolsLayer) {
            //clean other tools
            //TODO: etre générique sur l'ensemble des outils != Pan
            let pointer: Konva.Circle = stage.findOne(`#${ToolType.LabeledPoint}`);
            if (pointer) pointer.destroy();
            let crossline = stage.findOne("#crossline");
            if (crossline) crossline.destroy();
            if (!highlighted_point) {
                stage.container().style.cursor = "move";
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
        <Layer
            config={{ id: viewId }}
            on:wheel={(evt) => {
                evt.detail.evt.preventDefault(); // Prevent default scrolling
                let direction = evt.detail.evt.deltaY < 0 ? 1 : -1; // Get zoom direction
                // When we zoom on trackpad, e.evt.ctrlKey is true
                // In that case lets revert direction.
                if (evt.detail.evt.ctrlKey) direction = -direction;
                zoomFactor = zoom(
                    stage,
                    direction,
                    viewId,
                    POINTER_RADIUS,
                    POINTER_STROKEWIDTH,
                    RECT_STROKEWIDTH
                );
                //zoom reset highlighted point scaling
                if (highlighted_point) {
                    highlightPoint(highlighted_point);
                }
            }}
        >
            <KonvaImage
                config={{ image, id: imageId }}
                on:pointerdown={(event) => handleClickOnImage(event, imageId, viewId)}
                on:pointerup={(event) => handlePointerUpOnImage(event, viewId)}
            />
            <Group config={{ id: "masks" }} />
            <Group config={{ id: "masksGT" }} />
            <Group config={{ id: "input" }} />
        </Layer>
        <Layer config={{ name: "tools" }} bind:handle={toolsLayer} />
    </Stage>
</div>
<svelte:window on:keydown={handleKeyDown} />
