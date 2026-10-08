<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { lastFrameIndex } from "$lib/stores/videoStores.svelte";
  import type { DetectionTimelineLane } from "$lib/trackingTimeline";
  import { cn } from "$lib/ui";

  interface Props {
    lanes: DetectionTimelineLane[];
    onSelect: (trackId: number, startFrame: number) => void;
  }

  let { lanes, onSelect }: Props = $props();

  const totalFrames = $derived((lastFrameIndex.value ?? 0) + 1);

  function toLeftPct(frameIndex: number): number {
    return (frameIndex / totalFrames) * 100;
  }

  function toWidthPct(startFrame: number, endFrame: number): number {
    return Math.max(((endFrame - startFrame + 1) / totalFrames) * 100, 1);
  }
</script>

<div class="flex max-h-28 flex-col gap-0.5 overflow-y-auto" aria-label="Proposed tracks">
  {#each lanes as lane (lane.trackId)}
    <button
      type="button"
      class={cn(
        "flex h-3.5 w-full items-center gap-1.5 rounded-sm px-0.5 text-left transition-colors hover:bg-background/60",
        { "bg-background/70 ring-1 ring-primary/50": lane.state === "selected" },
        { "opacity-40": lane.state === "discarded" },
      )}
      title={lane.state === "discarded" ? `${lane.label} (discarded)` : lane.label}
      onclick={() => onSelect(lane.trackId, lane.segments[0]?.[0] ?? 0)}
    >
      <span
        class="w-20 shrink-0 truncate text-[9px] font-medium leading-none"
        style={`color: ${lane.color}`}
      >
        {lane.label}
      </span>
      <div class="relative h-2 flex-1 rounded-sm bg-muted/30">
        {#each lane.segments as [startFrame, endFrame], index (`${lane.trackId}-${index}`)}
          <div
            class="absolute top-0 h-2 rounded-sm"
            style={`left: ${toLeftPct(startFrame)}%; width: ${toWidthPct(startFrame, endFrame)}%; background: ${lane.color}`}
          ></div>
        {/each}
      </div>
    </button>
  {/each}
</div>
