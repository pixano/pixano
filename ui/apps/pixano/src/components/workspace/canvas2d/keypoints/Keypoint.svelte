<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import type Konva from "konva";
  import { Line } from "svelte-konva";

  import KeyPointCircle from "./KeypointsCircle.svelte";
  import type { KeypointVisibility } from "$lib/types/geometry";
  import type { KeypointAnnotation, KeypointVertex } from "$lib/types/shapeTypes";

  interface Props {
    keypointStructure: KeypointAnnotation;
    onPointChange?: (vertices: KeypointVertex[]) => void;
    zoomFactor: number;
    findPointCoordinate?: (point: number, type: "x" | "y") => number;
    color?: string;
    opacityOverride?: number;
    isPlaybackActive?: boolean;
    children?: import("svelte").Snippet;
  }

  let {
    keypointStructure,
    onPointChange = () => {},
    zoomFactor,
    findPointCoordinate = (point) => point,
    color = "rgba(135, 47, 100)",
    opacityOverride = -1,
    isPlaybackActive = false,
    children,
  }: Props = $props();

  let edges = $derived(keypointStructure.graph.edges);
  type EditableVertex = {
    x: number;
    y: number;
    features: KeypointVertex["features"];
  };
  /** Combined vertex data: position + metadata for editing. */
  let combinedVertices = $derived(
    keypointStructure.graph.vertices.map((v, i) => ({
      x: v.x,
      y: v.y,
      features: keypointStructure.vertexMetadata[i] ?? {
        state: "visible" as const,
        label: "",
        color: "",
      },
    })) as EditableVertex[],
  );
  let draftVertices = $state<EditableVertex[] | null>(null);
  let displayedVertices = $derived(draftVertices ?? combinedVertices);
  let keypointsId = $derived(keypointStructure.id);

  const onPointDragMove = (pointIndex: number, e: Konva.KonvaEventObject<DragEvent>) => {
    if (!keypointStructure.ui?.displayControl.editing) return;
    const pointPosition = (e.target as Konva.Circle).position();
    const source = draftVertices ?? combinedVertices;
    const updated = source.map((point, i) => {
      if (i === pointIndex) {
        return { ...point, x: pointPosition.x, y: pointPosition.y };
      }
      return point;
    });
    draftVertices = updated;
  };

  const onPointDragEnd = (pointIndex: number, e: Konva.KonvaEventObject<DragEvent>) => {
    if (!keypointStructure.ui?.displayControl.editing) return;
    const pointPosition = (e.target as Konva.Circle).position();
    const source = draftVertices ?? combinedVertices;
    const updated = source.map((point, i) => {
      if (i === pointIndex) {
        return { ...point, x: pointPosition.x, y: pointPosition.y };
      }
      return point;
    });
    draftVertices = updated;
    onPointChange(updated);
  };

  const onPointStateChange = (pointIndex: number, value: KeypointVisibility) => {
    const source = draftVertices ?? combinedVertices;
    const updated = source.map((point, i) => {
      if (i === pointIndex) {
        return { ...point, features: { ...point.features, state: value } };
      }
      return point;
    });
    draftVertices = updated;
    onPointChange(updated);
  };

  const findVertex = (index: number) => {
    const vertex = displayedVertices[index];
    const vertexX = findPointCoordinate(vertex.x, "x");
    const vertexY = findPointCoordinate(vertex.y, "y");
    return [vertexX, vertexY];
  };

  $effect(() => {
    // External updates after a commit should replace temporary drag state.
    // eslint-disable-next-line @typescript-eslint/no-unused-expressions
    keypointStructure.graph.vertices;
    draftVertices = null;
  });

  let opacity = $derived(
    opacityOverride >= 0
      ? opacityOverride
      : keypointStructure.ui?.displayControl.highlighted === "none"
        ? 0.3
        : 1,
  );
</script>

{@render children?.()}
{#each edges as line}
  <Line
    points={[...findVertex(line[0]), ...findVertex(line[1])]}
    stroke={color}
    strokeScaleEnabled={false}
    shadowForStrokeEnabled={false}
    {opacity}
  />
{/each}
{#if !isPlaybackActive}
  {#each displayedVertices as vertex, i}
    <KeyPointCircle
      vertexIndex={i}
      {zoomFactor}
      {vertex}
      {keypointsId}
      {color}
      {opacity}
      {onPointDragMove}
      {onPointDragEnd}
      {findPointCoordinate}
      draggable={keypointStructure.ui?.displayControl.editing ?? false}
      {onPointStateChange}
    />
  {/each}
{/if}
