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
  import type Konva from "konva";
  import { Rect } from "svelte-konva";
  import type { KeypointsTemplate, Shape } from "@pixano/core";

  import KeyPoints from "./keypoints/Keypoint.svelte";
  import { findRectBoundaries } from "../api/keypointsApi";

  export let stage: Konva.Stage;
  export let keypoints: KeypointsTemplate[] = [];
  export let newShape: Shape;
  export let zoomFactor: number;
  export let colorScale: (id: string) => string;
  export let viewId: string;

  const onDoubleClick = (keyPointsId: string) => {
    newShape = {
      status: "editing",
      shapeId: keyPointsId,
      highlighted: "self",
      type: "none",
    };
  };

  const onKeypointsChange = (vertices: KeypointsTemplate["vertices"], id: string) => {
    const image = stage.findOne(`#image-${viewId}`);
    const imageSize = image.getSize();
    const normalizedVertices = vertices.map((point) => ({
      ...point,
      x: point.x / imageSize.width,
      y: point.y / imageSize.height,
    }));
    newShape = {
      status: "editing",
      type: "keypoint",
      vertices: normalizedVertices,
      shapeId: id,
    };
  };
</script>

{#if keypoints}
  {#each keypoints as keypointStructure}
    {#if keypointStructure.visible}
      <KeyPoints
        onPointChange={(vertices) => onKeypointsChange(vertices, keypointStructure.id)}
        {stage}
        {keypointStructure}
        {zoomFactor}
        color={colorScale(keypointStructure.id)}
      >
        <Rect
          config={{
            x: findRectBoundaries(keypointStructure.vertices).x - 10 / zoomFactor,
            y: findRectBoundaries(keypointStructure.vertices).y - 10 / zoomFactor,
            width: findRectBoundaries(keypointStructure.vertices).width + 20 / zoomFactor,
            height: findRectBoundaries(keypointStructure.vertices).height + 20 / zoomFactor,
            fill: colorScale(keypointStructure.id),
            stroke: "rgba(135, 47, 100, 0.8)",
            id: "move-keyPoints-group",
            opacity: keypointStructure.editing ? 0.3 : 0,
          }}
          on:dblclick={() => onDoubleClick(keypointStructure.id)}
        />
      </KeyPoints>
    {/if}
  {/each}
{/if}