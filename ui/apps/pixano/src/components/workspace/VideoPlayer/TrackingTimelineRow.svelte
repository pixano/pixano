<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // The track being drawn by a tracking session: its parts and keyframes, on the timeline's
  // shared frame mapping.
  import { getTimelineLayoutContext } from "./timelineContext";
  import { frameToX, TIMELINE_HEADER_WIDTH } from "$lib/timeline/timelineGeometry";
  import {
    buildTrackingTimelineVisualState,
    type TrackingTimelineBarVisual,
    type TrackingTimelineState,
  } from "$lib/trackingTimeline";

  interface Props {
    state: TrackingTimelineState;
    /** The block height, its 4 px gap included. */
    height: number;
    laneWidth: number;
  }

  let { state, height, laneWidth }: Props = $props();

  const layout = getTimelineLayoutContext();
  const BAR_MIN_WIDTH = 6;
  const LABELS = { bbox: "New track", vos: "Mask tracking", detection: "Detection" } as const;

  const visualState = $derived(buildTrackingTimelineVisualState(state));
  const keyframeCount = $derived(visualState.markers.filter((m) => m.kind === "keyframe").length);

  // Clipped to the drawn window, so a pending bar never spans the whole zoomed lane.
  function barBox(bar: TrackingTimelineBarVisual): { left: number; width: number } | null {
    const start = frameToX(layout.geometry, bar.startFrame) - 3;
    const end = Math.max(frameToX(layout.geometry, bar.endFrame) + 3, start + BAR_MIN_WIDTH);
    const left = Math.max(start, layout.pxWindow.x0);
    const right = Math.min(end, layout.pxWindow.x1);
    return right > left ? { left, width: right - left } : null;
  }

  const completed = $derived(
    visualState.completedBars.map((bar, index) => ({ bar, index, box: barBox(bar) })),
  );
  const pending = $derived(
    visualState.pendingBar
      ? { bar: visualState.pendingBar, box: barBox(visualState.pendingBar) }
      : null,
  );
  const markers = $derived(
    visualState.markers
      .map((marker, index) => ({
        ...marker,
        index,
        x: frameToX(layout.geometry, marker.frameIndex),
      }))
      .filter((marker) => marker.x >= layout.pxWindow.x0 && marker.x <= layout.pxWindow.x1),
  );
</script>

<div class="flex" style:height="{height}px">
  <div class="sticky left-0 z-20 shrink-0 bg-card pt-1" style:width="{TIMELINE_HEADER_WIDTH}px">
    <div class="flex h-7 items-center gap-2 pl-3 pr-2">
      <span class="size-1.5 shrink-0 rounded-full bg-warning"></span>
      <span class="min-w-0 flex-1 truncate text-xs font-medium text-foreground">
        {LABELS[state.variant]}
      </span>
      <span class="shrink-0 font-mono text-[11px] tabular-nums text-foreground/65">
        {keyframeCount} kf
      </span>
    </div>
  </div>
  <div
    class="relative isolate mt-1 h-7 shrink-0 rounded-md bg-warning/5"
    style:width="{laneWidth}px"
  >
    {#each completed as { bar, index, box } (`completed-${bar.startFrame}-${bar.endFrame}-${index}`)}
      {#if box}
        <div
          class="absolute top-1.5 z-10 h-4 overflow-hidden rounded-sm border border-amber-300/25 bg-[linear-gradient(90deg,rgba(245,158,11,0.78)_0%,rgba(251,191,36,0.62)_100%)]"
          style:left="{box.left}px"
          style:width="{box.width}px"
        >
          {#if bar.label}
            <span
              class="absolute left-1 top-0 select-none truncate text-[9px] font-medium leading-4 text-white/95"
            >
              {bar.label}
            </span>
          {/if}
        </div>
      {/if}
    {/each}

    {#if pending?.box}
      <div
        class="tracking-timeline-pending absolute top-1.5 z-20 h-4 overflow-hidden rounded-sm border border-amber-100/65 motion-reduce:animate-none"
        style:left="{pending.box.left}px"
        style:width="{pending.box.width}px"
      >
        <span
          class="absolute left-1 top-0 select-none truncate text-[9px] font-medium leading-4 text-white/95"
        >
          {pending.bar.label}
        </span>
      </div>
    {/if}

    {#each markers as marker (`${marker.kind}-${marker.frameIndex}-${marker.index}`)}
      <div class="absolute top-1.5 z-30 h-4 w-2" style:left="{marker.x - 4}px">
        {#if marker.kind === "pending"}
          <div
            class="mx-auto mt-1 h-2 w-2 rotate-45 border-2 border-amber-100 bg-transparent"
          ></div>
        {:else}
          <div
            class="mx-auto mt-1 h-2 w-2 rotate-45 border border-amber-700 bg-amber-100 shadow-sm"
          ></div>
        {/if}
      </div>
    {/each}
  </div>
</div>

<style>
  @keyframes tracking-timeline-pending-sweep {
    0% {
      background-position:
        0% 0,
        0 0;
    }

    100% {
      background-position:
        220% 0,
        24px 0;
    }
  }

  .tracking-timeline-pending {
    background-image:
      linear-gradient(
        110deg,
        rgba(251, 191, 36, 0.22) 0%,
        rgba(245, 158, 11, 0.74) 48%,
        rgba(251, 191, 36, 0.22) 100%
      ),
      repeating-linear-gradient(
        45deg,
        rgba(255, 255, 255, 0.08) 0,
        rgba(255, 255, 255, 0.08) 10px,
        transparent 10px,
        transparent 20px
      );
    background-size:
      180% 100%,
      24px 24px;
    animation: tracking-timeline-pending-sweep 1.6s linear infinite;
  }

  @media (prefers-reduced-motion: reduce) {
    .tracking-timeline-pending {
      animation: none;
    }
  }
</style>
