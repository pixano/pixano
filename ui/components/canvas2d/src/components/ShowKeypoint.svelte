<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
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
      viewId,
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
      type: "keypoints",
      vertices: normalizedVertices,
      shapeId: id,
      viewId,
    };
  };
</script>

{#if keypoints}
  {#each keypoints as keypointStructure}
    {#if keypointStructure.visible && keypointStructure.view_id == viewId}
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
