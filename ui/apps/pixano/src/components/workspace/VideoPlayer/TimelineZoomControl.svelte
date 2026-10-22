<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Zoom out, slider, zoom in. The panel applies every change, so it can keep the playhead
  // (or the middle of the view) in place while the lanes widen.
  import { Slider, Tooltip } from "bits-ui";
  import { MagnifyingGlassMinus, MagnifyingGlassPlus } from "phosphor-svelte";

  import { TooltipContent } from "$lib/ui";
  import { nextTimelineZoom, TIMELINE_ZOOM_MIN } from "$lib/utils/timelineZoom";

  interface Props {
    zoom: number;
    max: number;
    onZoom: (zoom: number) => void;
  }

  let { zoom, max, onZoom }: Props = $props();

  const buttonClass =
    "flex h-7 w-7 items-center justify-center rounded-md text-foreground/65 transition-colors hover:bg-accent hover:text-foreground disabled:pointer-events-none disabled:opacity-40";
</script>

<div class="flex items-center gap-1">
  <Tooltip.Root>
    <Tooltip.Trigger
      type="button"
      class={buttonClass}
      aria-label="Zoom out"
      disabled={zoom <= TIMELINE_ZOOM_MIN}
      onclick={() => onZoom(nextTimelineZoom(zoom, -1, max))}
    >
      <MagnifyingGlassMinus class="h-4 w-4" />
    </Tooltip.Trigger>
    <TooltipContent><p>Zoom out</p></TooltipContent>
  </Tooltip.Root>
  <Slider.Root
    type="single"
    bind:value={() => zoom, (value) => onZoom(value)}
    min={TIMELINE_ZOOM_MIN}
    {max}
    class="relative flex w-16 touch-none select-none items-center @3xl:w-28"
  >
    <span class="relative h-1.5 w-full grow overflow-hidden rounded-full bg-muted">
      <Slider.Range class="absolute h-full bg-primary" />
    </span>
    <Slider.Thumb
      index={0}
      aria-label="Timeline zoom"
      class="block h-3.5 w-3.5 rounded-full border border-primary bg-background shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
    />
  </Slider.Root>
  <Tooltip.Root>
    <Tooltip.Trigger
      type="button"
      class={buttonClass}
      aria-label="Zoom in"
      disabled={zoom >= max}
      onclick={() => onZoom(nextTimelineZoom(zoom, 1, max))}
    >
      <MagnifyingGlassPlus class="h-4 w-4" />
    </Tooltip.Trigger>
    <TooltipContent><p>Zoom in</p></TooltipContent>
  </Tooltip.Root>
</div>
