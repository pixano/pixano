<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import {
    pendingKeyframeIndex,
    trackingKeyframeIndices,
    trackingSegmentRanges,
  } from "$lib/stores/trackingStore.svelte";
  import { lastFrameIndex } from "$lib/stores/videoStores.svelte";

  const totalFrames = $derived((lastFrameIndex.value ?? 0) + 1);
  const segments = $derived(trackingSegmentRanges.value);
  const keyframes = $derived(trackingKeyframeIndices.value);
  const pendingIdx = $derived(pendingKeyframeIndex.value);
  const hasMultipleSegments = $derived(segments.length > 1);
  const isSingleKeyframe = $derived(keyframes.length === 1);
</script>

<div
  class="relative h-5 w-full rounded-sm bg-[linear-gradient(90deg,rgba(245,158,11,0.06)_0%,rgba(245,158,11,0.02)_100%)]"
>
  {#each segments as [start, end], segIdx (segIdx)}
    {@const leftPct = (start / totalFrames) * 100}
    {@const rawWidthPct = ((end - start + 1) / totalFrames) * 100}
    {@const widthPct = Math.max(rawWidthPct, 2)}
    <div
      class="absolute top-0.5 h-4 rounded-sm border border-amber-300/25 bg-[linear-gradient(90deg,rgba(245,158,11,0.78)_0%,rgba(251,191,36,0.62)_100%)] shadow-[0_0_12px_rgba(245,158,11,0.18)]"
      style="left: {leftPct}%; width: {widthPct}%"
    >
      <span
        class="absolute left-1 top-0 text-[9px] leading-4 text-white/95 font-medium select-none truncate"
      >
        {#if hasMultipleSegments}
          Seg {segIdx + 1}
        {:else if isSingleKeyframe}
          1 keyframe — navigate to another frame and draw
        {:else}
          Tracking...
        {/if}
      </span>
    </div>
  {/each}
  {#each keyframes as kfIndex (kfIndex)}
    {@const kfPct = (kfIndex / totalFrames) * 100}
    <div class="absolute top-0.5 h-4 w-2 -translate-x-1/2" style="left: {kfPct}%">
      <div
        class="mx-auto mt-1 h-2 w-2 rotate-45 border border-amber-700 bg-amber-100 shadow-sm"
      ></div>
    </div>
  {/each}
  {#if pendingIdx !== null}
    {@const pendingPct = (pendingIdx / totalFrames) * 100}
    <div class="absolute top-0.5 h-4 w-2 -translate-x-1/2" style="left: {pendingPct}%">
      <div class="mx-auto mt-1 h-2 w-2 rotate-45 border-2 border-amber-100 bg-transparent"></div>
    </div>
  {/if}
</div>
