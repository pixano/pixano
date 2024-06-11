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

  import Keypoints from "./keypoints/Keypoints.svelte";

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

  $: keyPointStructure = {
    edges: newShape.keypoints.edges,
    vertices: newShape.keypoints.vertices,
    id: keypointsId,
    editing: true,
  } as KeypointsTemplate;
</script>

{#if newShape.viewId === viewId}
  <Group config={{ id: keypointsId, x: 0, y: 0 }}>
    <Keypoints {stage} {keyPointStructure} {zoomFactor} {findPointCoordinate} {onPointChange}>
      {#if newShape.status === "creating"}
        <Rect
          config={{
            x: newShape.x,
            y: newShape.y,
            width: newShape.width,
            height: newShape.height,
            fill: "rgba(135, 47, 100, 0.4)",
            id: "move-keyPoints-group",
          }}
        />
      {/if}
    </Keypoints>
  </Group>
{/if}
