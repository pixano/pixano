<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { lastFrameIndex } from "$lib/stores/videoStores.svelte";
  import {
    buildTrackingTimelineVisualState,
    type TrackingTimelineState,
  } from "$lib/trackingTimeline";

  interface Props {
    state: TrackingTimelineState;
  }

  let { state }: Props = $props();

  const totalFrames = $derived((lastFrameIndex.value ?? 0) + 1);
  const visualState = $derived(buildTrackingTimelineVisualState(state));

  function toLeftPct(frameIndex: number): number {
    return (frameIndex / totalFrames) * 100;
  }

  function toWidthPct(startFrame: number, endFrame: number): number {
    const rawWidthPct = ((endFrame - startFrame + 1) / totalFrames) * 100;
    return Math.max(rawWidthPct, 2);
  }
</script>

<div
  class="relative h-5 w-full rounded-sm bg-[linear-gradient(90deg,rgba(245,158,11,0.06)_0%,rgba(245,158,11,0.02)_100%)]"
>
  {#each visualState.completedBars as bar, barIndex (`completed-${bar.startFrame}-${bar.endFrame}-${barIndex}`)}
    <div
      class="absolute top-0.5 z-10 h-4 rounded-sm border border-amber-300/25 bg-[linear-gradient(90deg,rgba(245,158,11,0.78)_0%,rgba(251,191,36,0.62)_100%)] shadow-[0_0_12px_rgba(245,158,11,0.18)]"
      style={`left: ${toLeftPct(bar.startFrame)}%; width: ${toWidthPct(bar.startFrame, bar.endFrame)}%`}
    >
      {#if bar.label}
        <span
          class="absolute left-1 top-0 text-[9px] leading-4 text-white/95 font-medium select-none truncate"
        >
          {bar.label}
        </span>
      {/if}
    </div>
  {/each}

  {#if visualState.pendingBar}
    <div
      class="tracking-timeline-pending absolute top-0.5 z-20 h-4 rounded-sm border border-amber-100/65 shadow-[0_0_14px_rgba(245,158,11,0.20)]"
      style={`left: ${toLeftPct(visualState.pendingBar.startFrame)}%; width: ${toWidthPct(visualState.pendingBar.startFrame, visualState.pendingBar.endFrame)}%`}
    >
      <span
        class="absolute left-1 top-0 text-[9px] leading-4 text-white/95 font-medium select-none truncate"
      >
        {visualState.pendingBar.label}
      </span>
    </div>
  {/if}

  {#each visualState.markers as marker, markerIndex (`${marker.kind}-${marker.frameIndex}-${markerIndex}`)}
    <div
      class="absolute top-0.5 z-30 h-4 w-2 -translate-x-1/2"
      style={`left: ${toLeftPct(marker.frameIndex)}%`}
    >
      {#if marker.kind === "pending"}
        <div class="mx-auto mt-1 h-2 w-2 rotate-45 border-2 border-amber-100 bg-transparent"></div>
      {:else}
        <div
          class="mx-auto mt-1 h-2 w-2 rotate-45 border border-amber-700 bg-amber-100 shadow-sm"
        ></div>
      {/if}
    </div>
  {/each}
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
</style>
