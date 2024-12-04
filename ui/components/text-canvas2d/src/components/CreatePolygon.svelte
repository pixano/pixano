<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import Konva from "konva";
  import { Group, Line } from "svelte-konva";

  import type { Shape, Reference } from "@pixano/core";
  import type { PolygonGroupPoint } from "../lib/types/textCanvas2dTypes";
  import { runLengthEncode, convertPointToSvg } from "../api/maskApi";
  import { INPUTRECT_STROKEWIDTH } from "../lib/constants";
  import PolygonPoints from "./PolygonPoints.svelte";

  // Exports
  export let viewRef: Reference;
  export let selectedItemId: string;
  export let newShape: Shape;
  export let stage: Konva.Stage;
  export let currentImage: HTMLImageElement;
  export let zoomFactor: Record<string, number>;
  const POLYGON_ID = "creating";

  let polygonPoints: PolygonGroupPoint[][] = [];

  let isClosed = false;

  $: {
    if (newShape.status === "creating" && newShape.type === "mask") {
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

  function handlePolygonPointsClick(i: number, viewRef: Reference) {
    if (i === 0) {
      const svg = polygonPoints.map((point) => convertPointToSvg(point));
      const counts = runLengthEncode(svg, currentImage.width, currentImage.height);
      newShape = {
        status: "saving",
        masksImageSVG: [],
        rle: {
          counts,
          size: [currentImage.height, currentImage.width],
        },
        type: "mask",
        viewRef,
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

{#if "viewRef" in newShape && newShape.viewRef.name === viewRef.name}
  <Group config={{ id: "polygon", draggable: true }}>
    <Line
      config={{
        points: flatPoints,
        stroke: "hsl(316deg 60% 29.41%)",
        strokeWidth: INPUTRECT_STROKEWIDTH / zoomFactor[viewRef.name],
        fill: "#f9f4f773",
        closed: isClosed,
      }}
    />
    <PolygonPoints
      {viewRef}
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
