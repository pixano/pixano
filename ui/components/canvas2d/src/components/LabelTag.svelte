<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { Label, Tag, Text } from "svelte-konva";

  export let id: string;
  export let x: number;
  export let y: number;
  export let visible: boolean = true;
  export let zoomFactor: number;
  export let opacity: number = 1;
  export let tooltip: string | undefined;
  export let color: string;
</script>

<Label
  config={{
    id: `tooltip${id}`,
    x,
    y,
    width: 500,
    height: 50,
    offsetY: 12,
    visible: visible,
    scale: {
      x: 1 / zoomFactor,
      y: 1 / zoomFactor,
    },
    opacity: opacity,
  }}
>
  <Tag
    config={{
      fill: color,
      stroke: tooltip ? color : "transparent",
    }}
  />
  <Text
    config={{
      id: `text${id}`,
      x: 0,
      y: 0,
      text: tooltip,
      fontSize: 12,
      fontStyle: "100",
    }}
  />
</Label>
