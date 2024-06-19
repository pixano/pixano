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
  import { Group, Rect } from "svelte-konva";

  import type { CreateKeypointShape, KeypointsTemplate, SaveKeyBoxShape } from "@pixano/core";

  import Keypoints from "./keypoints/Keypoint.svelte";
  import { findRectBoundaries } from "../api/keypointsApi";

  export let zoomFactor: number;
  export let newShape: CreateKeypointShape | SaveKeyBoxShape;
  export let stage: Konva.Stage;
  export let viewId: string;

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

{#if newShape.viewId === viewId}
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
