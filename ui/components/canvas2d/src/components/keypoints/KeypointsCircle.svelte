<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { Circle } from "svelte-konva";

  import type { Vertex, VertexStates } from "@pixano/core";

  import type Konva from "konva";
  import LabelTag from "../LabelTag.svelte";
  import { onMount } from "svelte";

  export let stage: Konva.Stage;
  export let zoomFactor: number;
  export let vertex: Vertex;
  export let keypointsId: string;
  export let vertexIndex: number;
  export let draggable: boolean = false;
  export let color: string = "rgb(0,128,0)";
  export let opacity: number = 1;
  export let onPointDragMove: (pointId: number) => void;
  export let onPointStateChange: (pointId: number, value: VertexStates) => void;
  export let findPointCoordinate: (point: number, type: "x" | "y") => number = (point) => point;

  let showLabel = false;
  $: x = findPointCoordinate(vertex.x, "x");
  $: y = findPointCoordinate(vertex.y, "y");
  let menuNode: HTMLDivElement;

  const scaleCircleRadius = (id: number, scale: number) => {
    const point: Konva.Circle = stage.findOne(`#keypoint-${keypointsId}-${id}`);
    point.scaleX(scale);
    point.scaleY(scale);
  };

  const onMouseOver = () => {
    if (!draggable) return;
    scaleCircleRadius(vertexIndex, 2);
    showLabel = true;
  };

  const onMouseLeave = () => {
    scaleCircleRadius(vertexIndex, 1);
    showLabel = false;
  };

  const onCircleClick = (state: VertexStates) => {
    onPointStateChange(vertexIndex, state);
    menuNode.style.display = "none";
  };

  let fill = color;

  const defineFill = (features: Vertex["features"]) => {
    if (features.state === "invisible") return "transparent";
    if (features.state === "hidden") return "white";
    if (features?.color) return features.color;
    return color;
  };

  $: {
    fill = defineFill(vertex.features);
  }

  let hasStateFeature = !!vertex.features.state;

  onMount(() => {
    if (!hasStateFeature) return;
    const circle = stage.findOne(`#keypoint-${keypointsId}-${vertexIndex}`);
    circle.addEventListener("contextmenu", (e) => {
      if (!draggable) return;
      e.preventDefault();
      const target = e.target as unknown as Konva.Node;
      if (target === stage) return;
      menuNode.style.display = "block";
      menuNode.style.top = stage.getPointerPosition().y + "px";
      menuNode.style.left = stage.getPointerPosition().x + "px";
    });
  });
</script>

<div
  id="circle-menu"
  style="display: none;"
  class="absolute bg-white shadow-sm"
  bind:this={menuNode}
>
  <button
    class="block disabled:bg-slate-400 hover:bg-slate-200 p-2 w-full"
    on:click={() => onCircleClick("visible")}
    disabled={vertex.features.state === "visible"}>Visible</button
  >
  <button
    class="block disabled:bg-slate-400 hover:bg-slate-200 p-2 w-full"
    on:click={() => onCircleClick("hidden")}
    disabled={vertex.features.state === "hidden"}>Hidden</button
  >
  <button
    class="block disabled:bg-slate-400 hover:bg-slate-200 p-2 w-full"
    on:click={() => onCircleClick("invisible")}
    disabled={vertex.features.state === "invisible"}>Invisible</button
  >
</div>
<Circle
  config={{
    x,
    y,
    radius: 4 / zoomFactor,
    fill,
    stroke: "white",
    strokeWidth: 1 / zoomFactor,
    id: `keypoint-${keypointsId}-${vertexIndex}`,
    draggable,
    opacity,
    cancelBubble: true,
  }}
  on:dragmove={() => onPointDragMove(vertexIndex)}
  on:mouseover={onMouseOver}
  on:mouseleave={onMouseLeave}
/>
{#if vertex.features?.label}
  <LabelTag
    x={x + 16 / zoomFactor}
    {y}
    id={`${vertexIndex}`}
    visible={showLabel}
    {zoomFactor}
    color={vertex.features?.color || "white"}
    tooltip={vertex.features.label}
  />
{/if}
