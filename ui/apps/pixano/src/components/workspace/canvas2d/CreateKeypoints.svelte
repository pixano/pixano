<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { Group, Rect } from "svelte-konva";

  import type { Reference } from "$lib/types/dataset";
  import type { CreateKeypointShape, SaveKeyBoxShape } from "$lib/types/shapeTypes";
  import type { KeypointGraph } from "$lib/types/shapeTypes";
  import { initDisplayControl } from "$lib/types/dataset";

  import { findRectBoundaries } from "$lib/utils/keypointsUtils";
  import Keypoints from "./keypoints/Keypoint.svelte";

  interface Props {
    zoomFactor: number;
    newShape: CreateKeypointShape | SaveKeyBoxShape;
    viewRef: Reference;
    onNewShapeChange?: (shape: CreateKeypointShape | SaveKeyBoxShape) => void;
  }

  let {
    zoomFactor,
    newShape,
    viewRef,
    onNewShapeChange
  }: Props = $props();

  let keypointsId = ""; //filler value while we don't have the real values for id and template_id

  const findPointCoordinate = (point: number, type: "x" | "y") => {
    if (newShape.status === "creating") {
      return newShape[type] + point * (type === "x" ? newShape.width : newShape.height);
    }
    return point;
  };

  const onPointChange = (vertices: KeypointGraph["vertices"]) => {
    onNewShapeChange?.({
      ...newShape,
      keypoints: {
        ...newShape.keypoints,
        vertices,
      },
    });
  };

  let keypointStructure = $derived({
    edges: newShape.keypoints.edges,
    vertices: newShape.keypoints.vertices,
    id: newShape.keypoints.id ?? keypointsId,
    entityRef: { id: newShape.keypoints.entityRef?.id ?? "" },
    viewRef: newShape.viewRef,
    ui: {
      displayControl: { ...initDisplayControl, editing: true },
      top_entities: [],
    },
  } as KeypointGraph);

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
  <Group id={keypointsId} x={0} y={0}>
    <Keypoints {keypointStructure} {zoomFactor} {findPointCoordinate} onPointChange={onPointChange}>
      {#if newShape.status === "creating"}
        <Rect
          x={findCreationRectangleDimensions(newShape).x}
          y={findCreationRectangleDimensions(newShape).y}
          width={findCreationRectangleDimensions(newShape).width}
          height={findCreationRectangleDimensions(newShape).height}
          fill="rgba(135, 47, 100, 0.4)"
          stroke="rgba(135, 47, 100, 0.8)"
          id="move-keyPoints-group"
          opacity={keypointStructure.ui.displayControl.editing ? 0.3 : 0}
        />
      {/if}
    </Keypoints>
  </Group>
{/if}
