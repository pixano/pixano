<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { Rect } from "svelte-konva";

  import KeyPoints from "./keypoints/Keypoint.svelte";
  import { NEUTRAL_ENTITY_COLOR } from "$lib/constants/workspaceConstants";
  import type { Reference } from "$lib/types/dataset";
  import { ShapeType, type Shape } from "$lib/types/shapeTypes";
  import type { KeypointAnnotation, KeypointVertex } from "$lib/types/shapeTypes";
  import { findRectBoundaries } from "$lib/utils/keypointsUtils";

  interface Props {
    keypoints?: KeypointAnnotation[];
    newShape: Shape;
    zoomFactor: number;
    colorScale: (id: string) => string;
    viewRef: Reference;
    imageSize?: { width: number; height: number };
    isPlaybackActive?: boolean;
    onNewShapeChange?: (shape: Shape) => void;
  }

  let {
    keypoints = [],
    newShape,
    zoomFactor,
    colorScale,
    viewRef,
    imageSize = { width: 1, height: 1 },
    isPlaybackActive = false,
    onNewShapeChange,
  }: Props = $props();

  const onClick = (keypoint: KeypointAnnotation) => {
    onNewShapeChange?.({
      status: "editing",
      shapeId: keypoint.id,
      viewRef,
      highlighted: "self",
      top_entity_id: keypoint.ui?.top_entities ? keypoint.ui.top_entities[0].id : "",
      type: ShapeType.none,
    });
  };

  const onKeypointsChange = (vertices: KeypointVertex[], id: string) => {
    const normalizedVertices = vertices.map((point) => ({
      ...point,
      x: point.x / imageSize.width,
      y: point.y / imageSize.height,
    }));
    onNewShapeChange?.({
      status: "editing",
      type: ShapeType.keypoints,
      vertices: normalizedVertices,
      shapeId: id,
      viewRef,
    });
  };
</script>

{#if keypoints}
  {#each keypoints as keypointStructure}
    {#if !keypointStructure.ui?.displayControl.hidden && keypointStructure.viewRef?.name === viewRef.name}
      {@const colorId =
        (keypointStructure.ui?.top_entities ?? []).length > 0
          ? (keypointStructure.ui?.top_entities ?? [])[0].id
          : (keypointStructure.entityRef?.id ?? "")}
      {@const keypointColor =
        keypointStructure.ui?.displayControl.highlighted === "none"
          ? NEUTRAL_ENTITY_COLOR
          : colorScale(colorId)}
      <KeyPoints
        onPointChange={(vertices) => onKeypointsChange(vertices, keypointStructure.id)}
        {keypointStructure}
        {zoomFactor}
        color={keypointColor}
        {isPlaybackActive}
      >
        {@const bounds = findRectBoundaries(keypointStructure.graph.vertices)}
        <Rect
          x={bounds.x - 10 / zoomFactor}
          y={bounds.y - 10 / zoomFactor}
          width={bounds.width + 20 / zoomFactor}
          height={bounds.height + 20 / zoomFactor}
          fill={keypointColor}
          stroke={keypointStructure.ui?.displayControl.highlighted === "none"
            ? NEUTRAL_ENTITY_COLOR
            : "rgba(135, 47, 100, 0.8)"}
          id="move-keyPoints-group"
          opacity={keypointStructure.ui?.displayControl.editing ? 0.3 : 0}
          onclick={() => onClick(keypointStructure)}
        />
      </KeyPoints>
    {/if}
  {/each}
{/if}
