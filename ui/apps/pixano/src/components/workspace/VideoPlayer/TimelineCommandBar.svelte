<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // The player bar: playback and keyframe navigation, the current time, then the Pinned
  // filter and the zoom.
  import { Tooltip } from "bits-ui";
  import { CircleNotch, PushPin } from "phosphor-svelte";

  import TimelineZoomControl from "./TimelineZoomControl.svelte";
  import VideoControls from "./VideoControls.svelte";
  import { TooltipContent } from "$lib/ui";
  import { cn } from "$lib/utils/styleUtils";

  interface Props {
    time: string;
    buffering: boolean;
    pinnedCount: number;
    pinnedOnly: boolean;
    zoom: number;
    zoomMax: number;
    resetHighlight: () => void;
    onTogglePinnedOnly: () => void;
    onZoom: (zoom: number) => void;
  }

  let {
    time,
    buffering,
    pinnedCount,
    pinnedOnly,
    zoom,
    zoomMax,
    resetHighlight,
    onTogglePinnedOnly,
    onZoom,
  }: Props = $props();

  const pinnedTooltip = $derived(
    pinnedOnly
      ? "Show all objects"
      : pinnedCount > 0
        ? "Show pinned objects only"
        : "Pin objects to filter them",
  );
</script>

<div class="flex h-10 shrink-0 items-center justify-between gap-3 border-b border-border px-3">
  <div class="flex min-w-0 items-center gap-1.5">
    <VideoControls {resetHighlight} />
    <span class="mx-1 h-5 w-px shrink-0 bg-border" aria-hidden="true"></span>
    <span class="sr-only">Current time</span>
    <span
      class="flex h-7 shrink-0 items-center rounded-md bg-muted px-2 font-mono text-xs tabular-nums text-foreground"
    >
      {time}
    </span>
    {#if buffering}
      <span
        role="status"
        class="inline-flex h-7 shrink-0 items-center gap-1 rounded-md border border-warning/40 bg-warning/10 px-2 text-[11px] text-foreground"
      >
        <CircleNotch class="h-3 w-3 animate-spin" />
        Buffering
      </span>
    {/if}
  </div>

  <div class="flex shrink-0 items-center gap-2">
    <Tooltip.Root>
      <Tooltip.Trigger
        type="button"
        aria-pressed={pinnedOnly}
        aria-disabled={!pinnedOnly && pinnedCount === 0}
        onclick={onTogglePinnedOnly}
        class={cn(
          "inline-flex h-7 items-center gap-1.5 rounded-md border px-2 text-xs transition-colors",
          pinnedOnly
            ? "border-primary/40 bg-primary/15 text-foreground"
            : "border-border bg-muted/50 text-foreground/65 hover:text-foreground",
          !pinnedOnly && pinnedCount === 0 && "cursor-default opacity-60 hover:text-foreground/65",
        )}
      >
        <PushPin weight={pinnedOnly ? "fill" : "regular"} class="h-3.5 w-3.5" />
        Pinned
        <span class="font-mono tabular-nums">{pinnedCount}</span>
      </Tooltip.Trigger>
      <TooltipContent><p>{pinnedTooltip}</p></TooltipContent>
    </Tooltip.Root>
    <TimelineZoomControl {zoom} max={zoomMax} {onZoom} />
  </div>
</div>
