<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // The tracks a tracking-by-detection run proposes, one row each, on the timeline's shared
  // frame mapping. Clicking a row selects its track and moves the playhead to its start.
  import { getTimelineLayoutContext } from "./timelineContext";
  import { frameToX, TIMELINE_HEADER_WIDTH } from "$lib/timeline/timelineGeometry";
  import type { DetectionTimelineLane } from "$lib/trackingTimeline";
  import { cn } from "$lib/utils/styleUtils";

  interface Props {
    lanes: DetectionTimelineLane[];
    /** The block height of one lane, its 4 px gap included. */
    height: number;
    laneWidth: number;
    onSelect: (trackId: number, startFrame: number) => void;
  }

  let { lanes, height, laneWidth, onSelect }: Props = $props();

  const layout = getTimelineLayoutContext();
  const BAR_MIN_WIDTH = 4;

  function segmentBox([start, end]: [number, number]): { left: number; width: number } | null {
    const x0 = frameToX(layout.geometry, start) - 1;
    const x1 = Math.max(frameToX(layout.geometry, end) + 1, x0 + BAR_MIN_WIDTH);
    const left = Math.max(x0, layout.pxWindow.x0);
    const right = Math.min(x1, layout.pxWindow.x1);
    return right > left ? { left, width: right - left } : null;
  }
</script>

{#each lanes as lane (lane.trackId)}
  <div
    class={cn("flex", lane.state === "discarded" && "opacity-40")}
    style:height="{height}px"
    aria-label="Proposed track"
  >
    <div class="sticky left-0 z-20 shrink-0 bg-card pt-1" style:width="{TIMELINE_HEADER_WIDTH}px">
      <button
        type="button"
        class={cn(
          "flex h-5 w-full items-center gap-2 rounded-r-lg pl-3 pr-2 text-left transition-colors hover:bg-accent/60",
          lane.state === "selected" && "bg-timeline-row-selected",
        )}
        title={lane.state === "discarded" ? `${lane.label} (discarded)` : lane.label}
        aria-pressed={lane.state === "selected"}
        onclick={() => onSelect(lane.trackId, lane.segments[0]?.[0] ?? 0)}
      >
        <span class="size-2 shrink-0 rounded-full" style:background={lane.color}></span>
        <span class="min-w-0 flex-1 truncate text-[11px] font-medium text-foreground">
          {lane.label}
        </span>
      </button>
    </div>
    <div class="relative isolate mt-1 h-5 shrink-0" style:width="{laneWidth}px">
      {#each lane.segments as segment, index (`${lane.trackId}-${index}`)}
        {@const box = segmentBox(segment)}
        {#if box}
          <div
            class="absolute top-[7px] h-1.5 rounded-sm"
            style:left="{box.left}px"
            style:width="{box.width}px"
            style:background={lane.color}
          ></div>
        {/if}
      {/each}
    </div>
  </div>
{/each}
