<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import type { PointCloudColoring } from "$lib/pointcloud/coloring/colorMode.js";

  interface Props {
    legend: NonNullable<PointCloudColoring["legend"]>;
  }

  let { legend }: Props = $props();

  /**
   * Gradient stops sampled off the ramp. Enough to look continuous, few enough
   * to keep the inline style short — the ramp is piecewise linear over a handful
   * of anchors, so more stops would add nothing visible.
   */
  const GRADIENT_STOP_COUNT = 12;
  const PERCENT = 100;
  const RGB_MAX = 255;

  /** Significant digits shown for the bounds; the ramp is a rough read, not a measurement. */
  const BOUND_DIGITS = 3;

  const gradient = $derived.by(() => {
    const rgb = new Float32Array(3);
    const stops: string[] = [];
    for (let i = 0; i < GRADIENT_STOP_COUNT; i++) {
      const t = i / (GRADIENT_STOP_COUNT - 1);
      legend.ramp(t, rgb, 0);
      const channels = [rgb[0], rgb[1], rgb[2]].map((c) => Math.round(c * RGB_MAX)).join(" ");
      stops.push(`rgb(${channels}) ${(t * PERCENT).toFixed(0)}%`);
    }
    return `linear-gradient(to right, ${stops.join(", ")})`;
  });

  function format(value: number): string {
    const text = Number(value.toPrecision(BOUND_DIGITS)).toString();
    return legend.unit ? `${text} ${legend.unit}` : text;
  }
</script>

<div
  class="pointer-events-none absolute bottom-2 left-2 rounded bg-background/80 px-2 py-1.5 backdrop-blur-sm"
>
  <div class="h-1.5 w-40 rounded-full" style:background={gradient}></div>
  <!-- Three marks, not two: the scalar modes map by rank, so the middle colour
       sits at the median. Labelling only the ends would read as a linear scale
       and mislead about what a mid-ramp colour means. -->
  <div class="mt-1 flex w-40 justify-between text-[10px] leading-none text-muted-foreground">
    <span>{format(legend.low)}</span>
    <span>{format(legend.mid)}</span>
    <span>{format(legend.high)}</span>
  </div>
</div>
