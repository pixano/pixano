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

  import type { CreateKeyPointShape, KeyPointsTemplate, SaveKeyBoxShape } from "@pixano/core";

  import KeyPoints from "./keyPoints/KeyPoints.svelte";

  export let zoomFactor: number;
  export let newShape: CreateKeyPointShape | SaveKeyBoxShape;
  export let stage: Konva.Stage;
  export let viewId: string;

  let keyPointsId = "keyPoints";

  const findPointCoordinate = (point: number, type: "x" | "y") => {
    if (newShape.status === "creating") {
      return newShape[type] + point * (type === "x" ? newShape.width : newShape.height);
    }
    return point;
  };

  const onPointChange = (vertices: KeyPointsTemplate["vertices"]) => {
    newShape = {
      ...newShape,
      keyPoints: {
        ...newShape.keyPoints,
        vertices,
      },
    };
  };

  $: keyPointStructure = {
    edges: newShape.keyPoints.edges,
    vertices: newShape.keyPoints.vertices,
    id: keyPointsId,
    editing: true,
  } as KeyPointsTemplate;
</script>

{#if newShape.viewId === viewId}
  <Group config={{ id: keyPointsId, x: 0, y: 0 }}>
    <KeyPoints {stage} {keyPointStructure} {zoomFactor} {findPointCoordinate} {onPointChange}>
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
    </KeyPoints>
  </Group>
{/if}
