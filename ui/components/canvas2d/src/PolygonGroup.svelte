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
  import { Group, Line, Circle } from "svelte-konva";

  import type { DatasetItem, Shape } from "@pixano/core";

  // Exports
  export let viewId: string;
  export let selectedItemId: DatasetItem["id"];
  export let createNewShape: (shape: Shape) => void;
  export let stage: Konva.Stage;
  export let images: Record<string, HTMLImageElement> = {};
  export let polygonPoints: { x: number; y: number; id: number }[] = [];
  export let isCurrentPolygonClosed = false;
  export let canEdit = false;

  // POLYGON STATE
  $: flatPolygonPoints = polygonPoints.reduce((acc, val) => [...acc, val.x, val.y], [] as number[]);

  $: {
    if (polygonPoints.length === 0) {
      isCurrentPolygonClosed = false;
    }
  }

  function handlePolygonPointsDragMove(id: number) {
    const pos = stage.findOne(`#dot-${id}`).position();
    polygonPoints = polygonPoints.map((point) => {
      if (point.id === id) {
        return { ...point, x: pos.x, y: pos.y };
      }
      return point;
    });
  }

  function handlePolygonPointsClick(i: number, viewId: string) {
    if (i === 0) {
      isCurrentPolygonClosed = true;
      createNewShape({
        status: "inProgress",
        masksImageSVG: [],
        rle: {
          counts: flatPolygonPoints,
          size: [images[viewId].width, images[viewId].height],
        },
        type: "mask",
        viewId: viewId,
        itemId: selectedItemId,
        imageWidth: images[viewId].width,
        imageHeight: images[viewId].height,
        isManual: true,
      });
    }
  }
</script>

<Group config={{ id: "polygon", draggable: canEdit }}>
  {#if !!polygonPoints.length}
    <Line
      config={{
        points: flatPolygonPoints,
        stroke: "red",
        strokeWidth: 2,
        closed: isCurrentPolygonClosed,
        fill: "rgb(0,128,0,0.5)",
      }}
    />
  {/if}
  {#if canEdit}
    {#each polygonPoints as point, i}
      <Circle
        on:click={() => handlePolygonPointsClick(i, viewId)}
        on:dragmove={() => handlePolygonPointsDragMove(point.id)}
        config={{
          x: point.x,
          y: point.y,
          radius: 5,
          fill: "blue",
          stroke: "black",
          strokeWidth: 1,
          id: `dot-${point.id}`,
          draggable: true,
        }}
      />
    {/each}
  {/if}
</Group>
