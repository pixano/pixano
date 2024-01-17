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
  import { Group, Circle, Shape as KonvaShape, Path } from "svelte-konva";

  import type { DatasetItem, Shape } from "@pixano/core";
  import type { PolygonGroupDetails, PolygonGroupPoint } from "../lib/types/canvas2dTypes";
  import {
    sceneFunc,
    hexToRGBA,
    convertPointToSvg,
    parseSvgPath,
    runLengthEncode,
  } from "../api/maskApi";
  import { INPUTRECT_STROKEWIDTH } from "../lib/constants";

  // Exports
  export let viewId: string;
  export let selectedItemId: DatasetItem["id"];
  export let newShape: Shape;
  export let stage: Konva.Stage;
  export let images: Record<string, HTMLImageElement> = {};
  export let polygonDetails: PolygonGroupDetails;
  export let color: string;
  export let zoomFactor: Record<string, number>;

  let isCurrentPolygonClosed = polygonDetails.status === "created";
  let canEdit = false;
  let polygonShape: {
    simplifiedSvg: string[];
    simplifiedPoints: PolygonGroupPoint[][];
  } = {
    simplifiedSvg: polygonDetails.svg,
    simplifiedPoints: polygonDetails.svg.reduce(
      (acc, val) => [...acc, parseSvgPath(val)],
      [] as PolygonGroupPoint[][],
    ),
  };

  $: canEdit = polygonDetails.status === "creating" || polygonDetails.editing;

  $: {
    if (polygonDetails.id !== "creating") {
      polygonShape.simplifiedPoints = polygonDetails.svg.reduce(
        (acc, val) => [...acc, parseSvgPath(val)],
        [] as PolygonGroupPoint[][],
      );
    } else {
      polygonShape.simplifiedPoints = [polygonDetails.points];
    }
  }

  $: polygonShape.simplifiedSvg = polygonShape.simplifiedPoints.map((point) =>
    convertPointToSvg(point),
  );

  function handlePolygonPointsDragMove(id: number, i: number) {
    const pos = stage.findOne(`#dot-${polygonDetails.id}-${i}-${id}`).position();
    const newSimplifiedPoints = polygonShape.simplifiedPoints.map((points, pi) =>
      pi === i
        ? points.map((point) => (point.id === id ? { ...point, x: pos.x, y: pos.y } : point))
        : points,
    );
    polygonShape.simplifiedPoints = newSimplifiedPoints;
  }

  function handlePolygonPointsDragEnd() {
    const counts = runLengthEncode(
      polygonShape.simplifiedSvg,
      images[viewId].width,
      images[viewId].height,
    );

    if (polygonDetails.editing) {
      newShape = {
        status: "editing",
        type: "mask",
        maskId: polygonDetails.id,
        counts,
      };
    }
  }

  function handlePolygonPointsClick(i: number, viewId: string) {
    if (i === 0) {
      polygonShape.simplifiedPoints = [
        [...polygonShape.simplifiedPoints[0], polygonShape.simplifiedPoints[0][0]],
      ];
      const counts = runLengthEncode(
        polygonShape.simplifiedSvg,
        images[viewId].width,
        images[viewId].height,
      );
      newShape = {
        status: "inProgress",
        masksImageSVG: [],
        rle: {
          counts,
          size: [images[viewId].height, images[viewId].width],
        },
        type: "mask",
        viewId: viewId,
        itemId: selectedItemId,
        imageWidth: images[viewId].width,
        imageHeight: images[viewId].height,
        isManual: true,
      };
    }
  }

  function updateCircleRadius(id: number, i: number, radius: number) {
    const point: Konva.Circle = stage.findOne(`#dot-${polygonDetails.id}-${i}-${id}`);
    point.radius(radius);
  }
</script>

<Group config={{ id: "polygon", draggable: canEdit, visible: polygonDetails.visible }}>
  {#if canEdit}
    {#if polygonDetails.id === "creating"}
      <Path
        config={{
          data: polygonShape.simplifiedSvg[0],
          stroke: "hsl(316deg 60% 29.41%)",
          strokeWidth: INPUTRECT_STROKEWIDTH / zoomFactor[viewId],
          fill: "#f9f4f773",
        }}
      />
    {/if}
    <KonvaShape
      config={{
        sceneFunc: (ctx, stage) => sceneFunc(ctx, stage, polygonShape.simplifiedSvg),
        stroke: polygonDetails.status === "created" ? color : "hsl(316deg 60% 29.41%)",
        strokeWidth: 2 / zoomFactor[viewId],
        closed: isCurrentPolygonClosed,
        fill: polygonDetails.status === "created" ? hexToRGBA(color, 0.5) : "#f9f4f773",
      }}
    />
    {#each polygonShape.simplifiedPoints as shape, i}
      {#each shape as point, pi}
        <Circle
          on:click={() => handlePolygonPointsClick(pi, viewId)}
          on:dragmove={() => handlePolygonPointsDragMove(point.id, i)}
          on:dragend={handlePolygonPointsDragEnd}
          on:mouseover={(e) => {
            e.detail.target?.attrs?.id === `dot-${polygonDetails.id}-${i}-${point.id}` &&
              updateCircleRadius(point.id, i, 8 / zoomFactor[viewId]);
          }}
          on:mouseleave={() => updateCircleRadius(point.id, i, 4 / zoomFactor[viewId])}
          config={{
            x: point.x,
            y: point.y,
            radius: 4 / zoomFactor[viewId],
            fill: "rgb(0,128,0)",
            stroke: "white",
            strokeWidth: 1,
            id: `dot-${polygonDetails.id}-${i}-${point.id}`,
            draggable: true,
          }}
        />
      {/each}
    {/each}
  {:else}
    <KonvaShape
      config={{
        sceneFunc: (ctx, stage) => sceneFunc(ctx, stage, polygonDetails.svg),
        stroke: polygonDetails.status === "created" ? color : "hsl(316deg 60% 29.41%)",
        strokeWidth: polygonDetails.status === "created" ? 1 : 3,
        closed: isCurrentPolygonClosed,
        fill: polygonDetails.status === "created" ? hexToRGBA(color, 0.5) : "rgb(0,128,0,0.5)",
      }}
    />
  {/if}
</Group>
