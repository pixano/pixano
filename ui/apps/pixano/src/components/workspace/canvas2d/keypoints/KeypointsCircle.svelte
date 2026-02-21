<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import type Konva from "konva";
  import { Circle } from "svelte-konva";

  import type { KeypointVisibility } from "$lib/types/geometry";
  import type { KeypointVertex } from "$lib/types/shapeTypes";
  import LabelTag from "../LabelTag.svelte";

  interface Props {
    zoomFactor: number;
    vertex: KeypointVertex;
    keypointsId: string;
    vertexIndex: number;
    draggable?: boolean;
    color?: string;
    opacity?: number;
    onPointDragMove: (pointId: number, event: Konva.KonvaEventObject<DragEvent>) => void;
    onPointStateChange: (pointId: number, value: KeypointVisibility) => void;
    findPointCoordinate?: (point: number, type: "x" | "y") => number;
  }

  let {
    zoomFactor,
    vertex,
    keypointsId,
    vertexIndex,
    draggable = false,
    color = "rgb(0,128,0)",
    opacity = 1,
    onPointDragMove,
    onPointStateChange,
    findPointCoordinate = (point) => point,
  }: Props = $props();

  let showLabel = $state(false);
  let hoverScale = $state(1);
  let x = $derived(findPointCoordinate(vertex.x, "x"));
  let y = $derived(findPointCoordinate(vertex.y, "y"));
  let menuNode: HTMLDivElement = $state();

  const defineFill = (features: KeypointVertex["features"]) => {
    if (features.state === "invisible") return "transparent";
    if (features.state === "hidden") return "white";
    if (features?.color) return features.color;
    return color;
  };

  let fill = $derived(defineFill(vertex.features));

  const onMouseOver = () => {
    if (!draggable) return;
    hoverScale = 2;
    showLabel = true;
  };

  const onMouseLeave = () => {
    hoverScale = 1;
    showLabel = false;
  };

  const onCircleClick = (e: Konva.KonvaEventObject<MouseEvent>) => {
    if (!vertex.features.state || !draggable) return;
    e.evt.preventDefault();
    const target = e.target;
    if (!target) return;
    const stage = target.getStage();
    if (!stage) return;
    const pointerPos = stage.getPointerPosition();
    if (pointerPos && menuNode) {
      menuNode.style.display = "block";
      menuNode.style.top = pointerPos.y + "px";
      menuNode.style.left = pointerPos.x + "px";
    }
  };

  const hideMenu = () => {
    if (menuNode) menuNode.style.display = "none";
  };

  const onMenuClick = (state: KeypointVisibility) => {
    onPointStateChange(vertexIndex, state);
    if (menuNode) menuNode.style.display = "none";
  };
</script>

<div
  id="circle-menu"
  style="display: none;"
  class="absolute bg-card shadow-sm"
  role="menu"
  tabindex="-1"
  bind:this={menuNode}
  onpointerleave={hideMenu}
>
  <button
    class="block disabled:bg-muted hover:bg-accent p-2 w-full"
    onclick={() => onMenuClick("visible")}
    disabled={vertex.features.state === "visible"}
  >
    Visible
  </button>
  <button
    class="block disabled:bg-muted hover:bg-accent p-2 w-full"
    onclick={() => onMenuClick("hidden")}
    disabled={vertex.features.state === "hidden"}
  >
    Hidden
  </button>
  <button
    class="block disabled:bg-muted hover:bg-accent p-2 w-full"
    onclick={() => onMenuClick("invisible")}
    disabled={vertex.features.state === "invisible"}
  >
    Invisible
  </button>
</div>
<Circle
  {x}
  {y}
  radius={4 / zoomFactor}
  {fill}
  stroke="white"
  strokeWidth={1 / zoomFactor}
  shadowForStrokeEnabled={false}
  id={`keypoint-${keypointsId}-${vertexIndex}`}
  {draggable}
  {opacity}
  cancelBubble={true}
  scaleX={hoverScale}
  scaleY={hoverScale}
  ondragmove={(e: Konva.KonvaEventObject<DragEvent>) => onPointDragMove(vertexIndex, e)}
  onmouseover={onMouseOver}
  onmouseleave={onMouseLeave}
  onclick={onCircleClick}
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
