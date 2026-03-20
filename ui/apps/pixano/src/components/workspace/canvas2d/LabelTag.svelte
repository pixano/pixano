<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { Label, Tag, Text } from "svelte-konva";

  interface Props {
    id: string;
    x: number;
    y: number;
    visible?: boolean;
    zoomFactor: number;
    opacity?: number;
    tooltip: string | undefined;
    color: string;
  }

  let { id, x, y, visible = true, zoomFactor, opacity = 1, tooltip, color }: Props = $props();
</script>

<Label
  id={`tooltip${id}`}
  {x}
  {y}
  width={500}
  height={50}
  offsetY={12}
  {visible}
  scaleX={1 / zoomFactor}
  scaleY={1 / zoomFactor}
  {opacity}
>
  <Tag fill={color} stroke={tooltip ? color : "transparent"} />
  <Text id={`text${id}`} x={0} y={0} text={tooltip} fontSize={12} fontStyle="100" />
</Label>
