<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
--------------------------------------->

<script lang="ts">
  import type Konva from "konva";
  import { Line } from "svelte-konva";

  import type { KeypointAnnotation, KeypointVertex, KeypointVisibility } from "$lib/types/shapeTypes";
  import KeyPointCircle from "./KeypointsCircle.svelte";

  interface Props {
    keypointStructure: KeypointAnnotation;
    onPointChange?: (vertices: KeypointVertex[]) => void;
    zoomFactor: number;
    findPointCoordinate?: (point: number, type: "x" | "y") => number;
    color?: string;
    isPlaybackActive?: boolean;
    children?: import("svelte").Snippet;
  }

  let {
    keypointStructure,
    onPointChange = () => {},
    zoomFactor,
    findPointCoordinate = (point) => point,
    color = "rgba(135, 47, 100)",
    isPlaybackActive = false,
    children,
  }: Props = $props();

  let edges = $derived(keypointStructure.graph.edges);
  /** Combined vertex data: position + metadata for editing. */
  let combinedVertices = $derived(
    keypointStructure.graph.vertices.map((v, i) => ({
      x: v.x,
      y: v.y,
      features: keypointStructure.vertexMetadata[i] ?? { state: "visible" as const, label: "", color: "" },
    }))
  );
  let keypointsId = $derived(keypointStructure.id);

  const onPointDragMove = (pointIndex: number, e: Konva.KonvaEventObject<DragEvent>) => {
    if (!keypointStructure.ui?.displayControl.editing) return;
    const pointPosition = (e.target as Konva.Circle).position();
    const updated = combinedVertices.map((point, i) => {
      if (i === pointIndex) {
        return { ...point, x: pointPosition.x, y: pointPosition.y };
      }
      return point;
    });
    onPointChange(updated);
  };

  const onPointStateChange = (pointIndex: number, value: KeypointVisibility) => {
    const updated = combinedVertices.map((point, i) => {
      if (i === pointIndex) {
        return { ...point, features: { ...point.features, state: value } };
      }
      return point;
    });
    onPointChange(updated);
  };

  const findVertex = (index: number) => {
    const vertex = combinedVertices[index];
    const vertexX = findPointCoordinate(vertex.x, "x");
    const vertexY = findPointCoordinate(vertex.y, "y");
    return [vertexX, vertexY];
  };

  let opacity = $derived(keypointStructure.ui?.displayControl.highlighted === "none" ? 0.5 : 1);
</script>

{@render children?.()}
{#each edges as line}
  <Line
    points={[...findVertex(line[0]), ...findVertex(line[1])]}
    stroke={color}
    strokeWidth={keypointStructure.ui?.displayControl.highlighted === "self" ? 4 : 2 / zoomFactor}
    shadowForStrokeEnabled={false}
    {opacity}
  />
{/each}
{#if !isPlaybackActive}
  {#each combinedVertices as vertex, i}
    <KeyPointCircle
      vertexIndex={i}
      {zoomFactor}
      {vertex}
      {keypointsId}
      {color}
      {opacity}
      {onPointDragMove}
      {findPointCoordinate}
      draggable={keypointStructure.ui?.displayControl.editing ?? false}
      {onPointStateChange}
    />
  {/each}
{/if}
