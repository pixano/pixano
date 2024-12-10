<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { type KeypointsTemplate, type Reference, SaveShapeType, type Shape } from "@pixano/core";
  import type Konva from "konva";
  import { Rect } from "svelte-konva";

  import { findRectBoundaries } from "../api/keypointsApi";
  import KeyPoints from "./keypoints/Keypoint.svelte";

  export let stage: Konva.Stage;
  export let keypoints: KeypointsTemplate[] = [];
  export let newShape: Shape;
  export let zoomFactor: number;
  export let colorScale: (id: string) => string;
  export let viewRef: Reference;

  const onDoubleClick = (keyPointsId: string) => {
    newShape = {
      status: "editing",
      shapeId: keyPointsId,
      viewRef,
      highlighted: "self",
      type: "none",
    };
  };

  const onKeypointsChange = (vertices: KeypointsTemplate["vertices"], id: string) => {
    const image = stage.findOne(`#image-${viewRef.name}`);
    const imageSize = image.getSize();
    const normalizedVertices = vertices.map((point) => ({
      ...point,
      x: point.x / imageSize.width,
      y: point.y / imageSize.height,
    }));
    newShape = {
      status: "editing",
      type: SaveShapeType.keypoints,
      vertices: normalizedVertices,
      shapeId: id,
      viewRef,
    };
  };
</script>

{#if keypoints}
  {#each keypoints as keypointStructure}
    {#if !keypointStructure.ui.displayControl?.hidden && keypointStructure.viewRef.name === viewRef.name}
      <KeyPoints
        onPointChange={(vertices) => onKeypointsChange(vertices, keypointStructure.id)}
        {stage}
        {keypointStructure}
        {zoomFactor}
        color={colorScale(
          keypointStructure.ui.top_entities && keypointStructure.ui.top_entities.length > 0
            ? keypointStructure.ui.top_entities[0].id
            : keypointStructure.entityRef.id,
        )}
      >
        <Rect
          config={{
            x: findRectBoundaries(keypointStructure.vertices).x - 10 / zoomFactor,
            y: findRectBoundaries(keypointStructure.vertices).y - 10 / zoomFactor,
            width: findRectBoundaries(keypointStructure.vertices).width + 20 / zoomFactor,
            height: findRectBoundaries(keypointStructure.vertices).height + 20 / zoomFactor,
            fill: colorScale(
              keypointStructure.ui.top_entities && keypointStructure.ui.top_entities.length > 0
                ? keypointStructure.ui.top_entities[0].id
                : keypointStructure.entityRef.id,
            ),
            stroke: "rgba(135, 47, 100, 0.8)",
            id: "move-keyPoints-group",
            opacity: keypointStructure.ui.displayControl?.editing ? 0.3 : 0,
          }}
          on:dblclick={() => onDoubleClick(keypointStructure.id)}
        />
      </KeyPoints>
    {/if}
  {/each}
{/if}
