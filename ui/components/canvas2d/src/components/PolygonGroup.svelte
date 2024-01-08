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
  import type { PolygonGroupDetails } from "../lib/types/canvas2dTypes";

  // Exports
  export let viewId: string;
  export let selectedItemId: DatasetItem["id"];
  export let newShape: Shape;
  export let stage: Konva.Stage;
  export let images: Record<string, HTMLImageElement> = {};
  export let polygonDetails: PolygonGroupDetails;
  export let color: string;

  let isCurrentPolygonClosed = polygonDetails.status === "created";
  let canEdit = false;

  $: canEdit = polygonDetails.status === "creating" || polygonDetails.editing;

  $: flatPolygonPoints = polygonDetails.points.reduce(
    (acc, val) => [...acc, val.x, val.y],
    [] as number[],
  );

  $: {
    if (polygonDetails.points.length === 0) {
      isCurrentPolygonClosed = false;
    }
  }

  function handlePolygonPointsDragMove(id: number) {
    const pos = stage.findOne(`#dot-${id}`).position();
    polygonDetails.points = polygonDetails.points.map((point) => {
      if (point.id === id) {
        return { ...point, x: pos.x, y: pos.y };
      }
      return point;
    });
  }

  function handlePolygonPointsDragEnd() {
    if (polygonDetails.editing) {
      newShape = {
        status: "editingMask",
        maskId: polygonDetails.id,
        points: flatPolygonPoints,
      };
    }
  }

  function handlePolygonPointsClick(i: number, viewId: string) {
    if (i === 0) {
      isCurrentPolygonClosed = true;
      newShape = {
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
      };
    }
  }

  const hexToRGBA = (hex: string, alpha: number) => {
    const r = parseInt(hex.slice(1, 3), 16);
    const g = parseInt(hex.slice(3, 5), 16);
    const b = parseInt(hex.slice(5, 7), 16);
    return `rgba(${r},${g},${b},${alpha})`;
  };
</script>

<Group config={{ id: "polygon", draggable: canEdit, visible: polygonDetails.visible }}>
  {#if !!polygonDetails.points.length}
    <Line
      config={{
        points: flatPolygonPoints,
        stroke: polygonDetails.status === "created" ? color : "hsl(316deg 60% 29.41%)",
        strokeWidth: polygonDetails.status === "created" ? 1 : 3,
        closed: isCurrentPolygonClosed,
        fill: polygonDetails.status === "created" ? hexToRGBA(color, 0.5) : "rgb(0,128,0,0.5)",
      }}
    />
  {/if}
  {#if canEdit}
    {#each polygonDetails.points as point, i}
      <Circle
        on:click={() => handlePolygonPointsClick(i, viewId)}
        on:dragmove={() => handlePolygonPointsDragMove(point.id)}
        on:dragend={handlePolygonPointsDragEnd}
        config={{
          x: point.x,
          y: point.y,
          radius: 5,
          fill: "rgb(0,128,0)",
          stroke: "white",
          strokeWidth: 2,
          id: `dot-${point.id}`,
          draggable: true,
        }}
      />
    {/each}
  {/if}
</Group>
