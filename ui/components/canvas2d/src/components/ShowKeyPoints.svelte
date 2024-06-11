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

  import KeyPoints from "./keypoints/Keypoints.svelte";

  export let stage: Konva.Stage;
  export let keypoints: KeypointsTemplate[] = [];
  export let newShape: Shape;
  export let zoomFactor: number;
  export let colorScale: (id: string) => string;

  const onDoubleClick = (keyPointsId: string) => {
    newShape = {
      status: "editing",
      shapeId: keyPointsId,
      highlighted: "self",
      type: "none",
    };
  };

  const onKeyPointsChange = (vertices: KeypointsTemplate["vertices"], id: string) => {
    newShape = {
      status: "editing",
      type: "keypoint",
      vertices,
      shapeId: id,
    };
  };

  const findRectBoundaries = (vertices: KeypointsTemplate["vertices"]) => {
    const x = Math.min(...vertices.map((point) => point.x));
    const y = Math.min(...vertices.map((point) => point.y));
    const width = Math.max(...vertices.map((point) => point.x)) - x;
    const height = Math.max(...vertices.map((point) => point.y)) - y;
    return { x, y, width, height };
  };
</script>

{#if keypoints}
  {#each keypoints as keypointStructure}
    {#if keypointStructure.visible}
      <KeyPoints
        onPointChange={(vertices) => onKeyPointsChange(vertices, keypointStructure.id)}
        {stage}
        keyPointStructure={keypointStructure}
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
