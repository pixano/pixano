<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { Circle } from "svelte-konva";

  interface Props {
    x: number;
    y: number;
    radius: number;
    mode: "draw" | "erase";
  }

  let { x, y, radius, mode }: Props = $props();

  let cursorColor = $derived(mode === "draw" ? "rgba(0, 200, 0, 0.7)" : "rgba(200, 0, 0, 0.7)");
  let fillColor = $derived(mode === "draw" ? "rgba(0, 200, 0, 0.1)" : "rgba(200, 0, 0, 0.1)");
</script>

<Circle {x} {y} {radius} stroke={cursorColor} fill={fillColor} listening={false} />
