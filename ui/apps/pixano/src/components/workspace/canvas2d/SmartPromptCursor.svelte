<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { Circle, Group, Line, Rect } from "svelte-konva";

  import type { InteractivePromptMode } from "$lib/tools";

  interface Props {
    x: number;
    y: number;
    promptMode: InteractivePromptMode;
    stageWidth: number;
    stageHeight: number;
  }

  const BADGE_HALF_SIZE = 11;
  const OFFSET_X = 18;
  const OFFSET_Y = -18;

  function clamp(value: number, min: number, max: number): number {
    return Math.min(Math.max(value, min), max);
  }

  let { x, y, promptMode, stageWidth, stageHeight }: Props = $props();

  let anchor = $derived.by(() => ({
    x: clamp(
      x + OFFSET_X,
      BADGE_HALF_SIZE,
      Math.max(BADGE_HALF_SIZE, stageWidth - BADGE_HALF_SIZE),
    ),
    y: clamp(
      y + OFFSET_Y,
      BADGE_HALF_SIZE,
      Math.max(BADGE_HALF_SIZE, stageHeight - BADGE_HALF_SIZE),
    ),
  }));

  let palette = $derived.by(() => {
    if (promptMode === "positive") {
      return {
        stroke: "rgba(16, 185, 129, 0.98)",
        fill: "rgba(16, 185, 129, 0.18)",
      };
    }
    if (promptMode === "negative") {
      return {
        stroke: "rgba(244, 63, 94, 0.98)",
        fill: "rgba(244, 63, 94, 0.18)",
      };
    }
    return {
      stroke: "rgba(226, 232, 240, 0.98)",
      fill: "rgba(15, 23, 42, 0.28)",
    };
  });
</script>

<Group listening={false}>
  {#if promptMode === "box"}
    <Rect
      x={anchor.x - 10}
      y={anchor.y - 10}
      width={20}
      height={20}
      cornerRadius={4}
      stroke="rgba(255, 255, 255, 0.9)"
      strokeWidth={4}
      opacity={0.5}
      listening={false}
    />
    <Rect
      x={anchor.x - 10}
      y={anchor.y - 10}
      width={20}
      height={20}
      cornerRadius={4}
      fill={palette.fill}
      stroke={palette.stroke}
      strokeWidth={1.5}
      listening={false}
    />
    <Line
      points={[anchor.x - 4, anchor.y - 4, anchor.x + 4, anchor.y - 4, anchor.x + 4, anchor.y + 4]}
      stroke={palette.stroke}
      strokeWidth={1.5}
      lineCap="round"
      lineJoin="round"
      listening={false}
    />
  {:else}
    <Circle
      x={anchor.x}
      y={anchor.y}
      radius={10}
      stroke="rgba(255, 255, 255, 0.9)"
      strokeWidth={4}
      opacity={0.5}
      listening={false}
    />
    <Circle
      x={anchor.x}
      y={anchor.y}
      radius={10}
      fill={palette.fill}
      stroke={palette.stroke}
      strokeWidth={1.5}
      listening={false}
    />
    <Line
      points={[anchor.x - 4.5, anchor.y, anchor.x + 4.5, anchor.y]}
      stroke={palette.stroke}
      strokeWidth={1.75}
      lineCap="round"
      listening={false}
    />
    {#if promptMode === "positive"}
      <Line
        points={[anchor.x, anchor.y - 4.5, anchor.x, anchor.y + 4.5]}
        stroke={palette.stroke}
        strokeWidth={1.75}
        lineCap="round"
        listening={false}
      />
    {/if}
  {/if}
</Group>
