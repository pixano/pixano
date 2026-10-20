<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // The thin strip under the ruler: how many tracked objects are present along the clip.
  import { interpolatePlasma } from "d3";

  import { getTimelineLayoutContext } from "./timelineContext";
  import { buildDensityBuckets } from "$lib/timeline/densityBuckets";
  import { frameToX } from "$lib/timeline/timelineGeometry";
  import { effectProbe } from "$lib/utils/effectProbe";

  interface Props {
    laneWidth: number;
    spans: ReadonlyArray<{ start: number; end: number }>;
  }

  let { laneWidth, spans }: Props = $props();

  const layout = getTimelineLayoutContext();
  const STRIP_HEIGHT = 3;

  const buckets = $derived.by(() => {
    effectProbe("Timeline.density");
    return buildDensityBuckets(spans, layout.geometry.lastFrame + 1);
  });
  const x0 = $derived(layout.pxWindow.x0);
  const svgWidth = $derived(Math.max(0, layout.pxWindow.x1 - layout.pxWindow.x0));
  // A one-frame clip has a single bucket: it spans the whole lane.
  const rects = $derived(
    buckets
      .map((bucket) => ({
        key: bucket.index,
        x: buckets.length === 1 ? -x0 : frameToX(layout.geometry, bucket.startFrame) - x0,
        width:
          buckets.length === 1
            ? laneWidth
            : (bucket.endFrame - bucket.startFrame) * layout.geometry.pxPerFrame,
        color: interpolatePlasma(bucket.normalized),
      }))
      .filter((rect) => rect.x + rect.width >= 0 && rect.x <= svgWidth),
  );
</script>

<div class="relative h-1 bg-card pt-px" style:width="{laneWidth}px" aria-hidden="true">
  <svg
    class="pointer-events-none absolute top-px"
    style:left="{x0}px"
    width={svgWidth}
    height={STRIP_HEIGHT}
    viewBox="0 0 {svgWidth} {STRIP_HEIGHT}"
    preserveAspectRatio="none"
  >
    {#each rects as rect (rect.key)}
      <rect x={rect.x} y="0" width={rect.width} height={STRIP_HEIGHT} fill={rect.color} />
    {/each}
  </svg>
</div>
