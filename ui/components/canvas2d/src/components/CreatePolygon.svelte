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
  import { Group, Line } from "svelte-konva";

  import type { DatasetItem, Shape } from "@pixano/core";
  import type { PolygonGroupPoint } from "../lib/types/canvas2dTypes";
  import { runLengthEncode, convertPointToSvg } from "../api/maskApi";
  import { INPUTRECT_STROKEWIDTH } from "../lib/constants";
  import PolygonPoints from "./PolygonPoints.svelte";

  // Exports
  export let viewId: string;
  export let selectedItemId: DatasetItem["id"];
  export let newShape: Shape;
  export let stage: Konva.Stage;
  export let currentImage: HTMLImageElement;
  export let zoomFactor: Record<string, number>;
  const POLYGON_ID = "creating";

  let polygonPoints: PolygonGroupPoint[][] = [];

  let isClosed = false;

  $: {
    if (newShape.status === "creating") {
      const lastPolygonDetailsPoint = newShape.points.at(-1);
      const lastSimplifiedPoint = polygonPoints?.[0]?.at(-1);
      if (lastPolygonDetailsPoint && lastPolygonDetailsPoint?.id !== lastSimplifiedPoint?.id) {
        polygonPoints = [[...(polygonPoints[0] || []), lastPolygonDetailsPoint]];
      }
      if (newShape.points.length === 0) {
        polygonPoints = [];
      }
    }
    if (newShape.status === "none") {
      polygonPoints = [];
      isClosed = false;
    }
  }

  function handlePolygonPointsClick(i: number, viewId: string) {
    if (i === 0) {
      const svg = polygonPoints.map((point) => convertPointToSvg(point));
      const counts = runLengthEncode(svg, currentImage.width, currentImage.height);
      newShape = {
        status: "inProgress",
        masksImageSVG: [],
        rle: {
          counts,
          size: [currentImage.height, currentImage.width],
        },
        type: "mask",
        viewId: viewId,
        itemId: selectedItemId,
        imageWidth: currentImage.width,
        imageHeight: currentImage.height,
      };
      isClosed = true;
    }
  }

  function handlePolygonPointsDragMove(id: number, i: number) {
    const pos = stage.findOne(`#dot-${POLYGON_ID}-${i}-${id}`).position();
    const newPolygonPoints = polygonPoints.map((points, pi) =>
      pi === i
        ? points.map((point) => (point.id === id ? { ...point, x: pos.x, y: pos.y } : point))
        : points,
    );
    polygonPoints = newPolygonPoints;
  }

  $: flatPoints = polygonPoints[0]?.reduce((acc, val) => [...acc, val.x, val.y], [] as number[]);
</script>

{#if "viewId" in newShape && newShape.viewId === viewId}
  <Group config={{ id: "polygon", draggable: true }}>
    <Line
      config={{
        points: flatPoints,
        stroke: "hsl(316deg 60% 29.41%)",
        strokeWidth: INPUTRECT_STROKEWIDTH / zoomFactor[viewId],
        fill: "#f9f4f773",
        closed: isClosed,
      }}
    />
    <PolygonPoints
      {viewId}
      {stage}
      {zoomFactor}
      polygonId={POLYGON_ID}
      points={polygonPoints}
      {handlePolygonPointsClick}
      {handlePolygonPointsDragMove}
      handlePolygonPointsDragEnd={null}
    />
  </Group>
{/if}
