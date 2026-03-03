<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { trackingKeyframeIndices, trackingSegmentRanges, pendingKeyframeIndex } from "$lib/stores/trackingStore.svelte";
  import { lastFrameIndex } from "$lib/stores/videoStores.svelte";

  const totalFrames = $derived((lastFrameIndex.value ?? 0) + 1);
  const segments = $derived(trackingSegmentRanges.value);
  const keyframes = $derived(trackingKeyframeIndices.value);
  const pendingIdx = $derived(pendingKeyframeIndex.value);
  const hasMultipleSegments = $derived(segments.length > 1);
  const isSingleKeyframe = $derived(keyframes.length === 1);
</script>

<div class="relative h-6 w-full">
  {#each segments as [start, end], segIdx (segIdx)}
    {@const leftPct = (start / totalFrames) * 100}
    {@const rawWidthPct = ((end - start + 1) / totalFrames) * 100}
    {@const widthPct = Math.max(rawWidthPct, 2)}
    <div
      class="absolute top-1 h-4 rounded-sm bg-amber-500/60"
      style="left: {leftPct}%; width: {widthPct}%"
    >
      <span class="absolute left-1 top-0 text-[10px] leading-4 text-white font-medium select-none truncate">
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
    <div
      class="absolute top-1 h-4 w-2 -translate-x-1/2"
      style="left: {kfPct}%"
    >
      <div class="h-2 w-2 rotate-45 bg-amber-300 border border-amber-600 mx-auto mt-1"></div>
    </div>
  {/each}
  {#if pendingIdx !== null}
    {@const pendingPct = (pendingIdx / totalFrames) * 100}
    <div
      class="absolute top-1 h-4 w-2 -translate-x-1/2"
      style="left: {pendingPct}%"
    >
      <div class="h-2 w-2 rotate-45 border-2 border-amber-300 bg-transparent mx-auto mt-1"></div>
    </div>
  {/if}
</div>
