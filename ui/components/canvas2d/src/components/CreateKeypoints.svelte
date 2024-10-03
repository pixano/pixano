<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import Konva from "konva";
  import { Group, Rect } from "svelte-konva";

  import type {
    CreateKeypointShape,
    KeypointsTemplate,
    SaveKeyBoxShape,
    Reference,
  } from "@pixano/core";

  import Keypoints from "./keypoints/Keypoint.svelte";
  import { findRectBoundaries } from "../api/keypointsApi";

  export let zoomFactor: number;
  export let newShape: CreateKeypointShape | SaveKeyBoxShape;
  export let stage: Konva.Stage;
  export let viewRef: Reference;

  let keypointsId = "keyPoints";

  const findPointCoordinate = (point: number, type: "x" | "y") => {
    if (newShape.status === "creating") {
      return newShape[type] + point * (type === "x" ? newShape.width : newShape.height);
    }
    return point;
  };

  const onPointChange = (vertices: KeypointsTemplate["vertices"]) => {
    newShape = {
      ...newShape,
      keypoints: {
        ...newShape.keypoints,
        vertices,
      },
    };
  };

  $: keypointStructure = {
    edges: newShape.keypoints.edges,
    vertices: newShape.keypoints.vertices,
    id: keypointsId,
    viewRef: newShape.viewRef,
    editing: true,
  } as KeypointsTemplate;

  const findCreationRectangleDimensions = (shape: CreateKeypointShape) => {
    const { x, y, width, height } = findRectBoundaries(keypointStructure.vertices);
    return {
      x: x * shape.width + shape.x,
      y: y * shape.height + shape.y,
      width: width * shape.width,
      height: height * shape.height,
    };
  };
</script>

{#if newShape.viewRef.name === viewRef.name}
  <Group config={{ id: keypointsId, x: 0, y: 0 }}>
    <Keypoints {stage} {keypointStructure} {zoomFactor} {findPointCoordinate} {onPointChange}>
      {#if newShape.status === "creating"}
        <Rect
          config={{
            x: findCreationRectangleDimensions(newShape).x,
            y: findCreationRectangleDimensions(newShape).y,
            width: findCreationRectangleDimensions(newShape).width,
            height: findCreationRectangleDimensions(newShape).height,
            fill: "rgba(135, 47, 100, 0.4)",
            stroke: "rgba(135, 47, 100, 0.8)",
            id: "move-keyPoints-group",
            opacity: keypointStructure.editing ? 0.3 : 0,
          }}
        />
      {/if}
    </Keypoints>
  </Group>
{/if}
