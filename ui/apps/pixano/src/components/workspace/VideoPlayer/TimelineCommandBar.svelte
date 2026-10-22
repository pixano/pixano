<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // The player bar: playback and keyframe navigation, the current time, the cameras, then
  // the zoom.
  import { CircleNotch } from "phosphor-svelte";

  import TimelineViewSwitch from "./TimelineViewSwitch.svelte";
  import TimelineZoomControl from "./TimelineZoomControl.svelte";
  import VideoControls from "./VideoControls.svelte";

  interface Props {
    time: string;
    buffering: boolean;
    zoom: number;
    zoomMax: number;
    /** The record's cameras; the view switch shows only with several. */
    views: readonly string[];
    viewFilter: string | null;
    onSelectView: (view: string | null) => void;
    resetHighlight: () => void;
    onZoom: (zoom: number) => void;
  }

  let {
    time,
    buffering,
    zoom,
    zoomMax,
    views,
    viewFilter,
    onSelectView,
    resetHighlight,
    onZoom,
  }: Props = $props();
</script>

<!-- Narrow panels drop the slider's length, and the camera buttons become a menu
     (container queries). -->
<div
  class="@container flex h-10 shrink-0 items-center justify-between gap-3 border-b border-border px-3"
>
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
    {#if views.length > 1}
      <span class="mx-1 hidden h-5 w-px shrink-0 bg-border @3xl:block" aria-hidden="true"></span>
      <TimelineViewSwitch {views} selected={viewFilter} onSelect={onSelectView} />
    {/if}
  </div>

  <div class="flex shrink-0 items-center gap-2">
    <TimelineZoomControl {zoom} max={zoomMax} {onZoom} />
  </div>
</div>
