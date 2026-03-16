<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { Group, Line } from "svelte-konva";

  import type { Point2D } from "$lib/types/geometry";

  interface Props {
    position: Point2D | null;
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
      opacity={0.75}
      dash={[5, 1]}
      listening={false}
    />
    <Line
      points={[0, position.y, stageWidth, position.y]}
      stroke="white"
      opacity={0.75}
      dash={[5, 1]}
      listening={false}
    />
  </Group>
{/if}
