<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // A lane's presence lines, keyframe ticks, start/end caps and merged bands, drawn for the
  // visible window only: a few paths per color, rebuilt when the lane, the zoom or the window
  // changes, never on a frame change.
  import { getTimelineLayoutContext } from "./timelineContext";
  import { buildLaneMarks, lanePathData } from "$lib/timeline/trackMarks";
  import type { LaneGeom, MarkGeometry } from "$lib/timeline/types";
  import { effectProbe } from "$lib/utils/effectProbe";

  interface Props {
    lane: LaneGeom;
    geo: MarkGeometry;
    /** Opacity of the presence lines; ticks and caps are always opaque. */
    lineOpacity: number;
    showTicks?: boolean;
    /** False for rows scrolled far out of view: they draw nothing. */
    visible?: boolean;
  }

  let { lane, geo, lineOpacity, showTicks = true, visible = true }: Props = $props();

  const layout = getTimelineLayoutContext();

  const x0 = $derived(layout.pxWindow.x0);
  const width = $derived(Math.max(0, layout.pxWindow.x1 - layout.pxWindow.x0));
  const paths = $derived.by(() => {
    if (!visible || width === 0 || (lane.spans.length === 0 && lane.frames.length === 0)) {
      return [];
    }
    effectProbe("Timeline.trackMarks");
    return buildLaneMarks(lane, layout.geometry, layout.frameWindow, layout.pxWindow, {
      showTicks,
    }).map((group) => ({ color: group.color, ...lanePathData(group, geo, layout.dpr, x0) }));
  });
</script>

{#if paths.length > 0}
  <svg
    class="pointer-events-none absolute top-0"
    style:left="{x0}px"
    {width}
    height={geo.rowHeight}
    viewBox="0 0 {width} {geo.rowHeight}"
    aria-hidden="true"
  >
    {#each paths as path (path.color)}
      {#if path.lines}
        <path d={path.lines} fill={path.color} fill-opacity={lineOpacity} />
      {/if}
      {#if path.bands}
        <path d={path.bands} fill={path.color} fill-opacity="0.55" />
      {/if}
      {#if path.ticks}
        <path
          d={path.ticks}
          fill="none"
          stroke={path.color}
          stroke-width={geo.tick.w}
          stroke-linecap="round"
        />
      {/if}
      {#if path.caps}
        <path
          d={path.caps}
          fill="none"
          stroke={path.color}
          stroke-width={geo.cap.w}
          stroke-linecap="round"
        />
      {/if}
    {/each}
  </svg>
{/if}
