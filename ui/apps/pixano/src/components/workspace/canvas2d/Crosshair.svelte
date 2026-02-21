<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { Group, Line } from "svelte-konva";

  interface Props {
    position: { x: number; y: number } | null;
    stageWidth: number;
    stageHeight: number;
  }

  let { position, stageWidth, stageHeight }: Props = $props();
</script>

{#if position}
  <Group id="crossline">
    <Line
      points={[position.x, 0, position.x, stageHeight]}
      stroke="white"
      strokeWidth={1}
      opacity={0.75}
      dash={[5, 1]}
      listening={false}
    />
    <Line
      points={[0, position.y, stageWidth, position.y]}
      stroke="white"
      strokeWidth={1}
      opacity={0.75}
      dash={[5, 1]}
      listening={false}
    />
  </Group>
{/if}
