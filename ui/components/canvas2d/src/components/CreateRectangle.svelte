<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { Rect, Group } from "svelte-konva";

  import { INPUTRECT_STROKEWIDTH } from "../lib/constants";

  import LabelTag from "./LabelTag.svelte";
  import type { CreateRectangleShape, SaveRectangleShape } from "@pixano/core";
  import type Konva from "konva";

  export let zoomFactor: number;
  export let newShape: CreateRectangleShape | SaveRectangleShape;
  export let stage: Konva.Stage;
  export let viewId: string;

  let rectangleGroup: Konva.Group;

  let x: number;
  let y: number;
  let width: number;
  let height: number;
  let labelX: number;
  let labelY: number;

  $: {
    if (newShape.status === "creating") {
      const rect = rectangleGroup?.findOne("#drag-rect");
      if (rect) {
        const viewLayer: Konva.Layer = stage.findOne(`#${viewId}`);
        const correctedRect = rect.getClientRect({
          skipTransform: false,
          skipShadow: true,
          skipStroke: true,
          relativeTo: viewLayer,
        });
        x = newShape.x;
        y = newShape.y;
        width = newShape.width;
        height = newShape.height;
        labelX = correctedRect?.x;
        labelY = correctedRect?.y;
      }
    }
  }
</script>

{#if newShape.viewId === viewId}
  <Group bind:handle={rectangleGroup} config={{ id: "drag-rect-group" }}>
    <Rect
      config={{
        id: "drag-rect",
        x,
        y,
        width,
        height,
        stroke: "hsl(316deg 60% 29.41%)",
        fill: "#f9f4f773",
        strokeWidth: INPUTRECT_STROKEWIDTH / zoomFactor,
        listening: false,
      }}
    />
    {#if labelX && labelY}
      <LabelTag
        id="drag-rect-tag"
        x={labelX}
        y={labelY}
        {zoomFactor}
        tooltip={`${Math.round(Math.abs(width))}px x ${Math.round(Math.abs(height))}px`}
        color="#fff"
      />
    {/if}
  </Group>
{/if}
