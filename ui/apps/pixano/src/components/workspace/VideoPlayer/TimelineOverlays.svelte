<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // What moves over the rows: the playhead line, the selected keyframe, the hovered tick and
  // its tooltip. Single elements moved with transforms, so a frame change costs a few style
  // writes and no lane re-render.
  import type { OverlayMark, OverlayTooltip } from "./timelineContext";
  import { TIMELINE_HEADER_WIDTH } from "$lib/timeline/timelineGeometry";

  interface Props {
    /** The playhead's x in lane px. */
    playheadX: number;
    bodyHeight: number;
    selected: OverlayMark | null;
    hover: OverlayMark | null;
    tooltip: OverlayTooltip | null;
    /** Scroll offsets of the panel, to keep the tooltip inside the visible lanes. */
    scrollLeft: number;
    scrollTop: number;
    viewportWidth: number;
  }

  let {
    playheadX,
    bodyHeight,
    selected,
    hover,
    tooltip,
    scrollLeft,
    scrollTop,
    viewportWidth,
  }: Props = $props();

  const TOOLTIP_HEIGHT = 20;
  const TOOLTIP_CHAR_WIDTH = 6.6;

  // Above its row, or below when the sticky ruler would cover it; clamped to the visible lanes.
  const tooltipBox = $derived.by(() => {
    if (!tooltip) return null;
    const width = tooltip.text.length * TOOLTIP_CHAR_WIDTH + 12;
    const minLeft = scrollLeft + 4;
    const maxLeft = Math.max(minLeft, scrollLeft + viewportWidth - width - 4);
    const left = Math.min(maxLeft, Math.max(minLeft, tooltip.x - width / 2));
    const above = tooltip.rowTop - TOOLTIP_HEIGHT - 2;
    const top = above < scrollTop ? tooltip.rowTop + tooltip.rowHeight + 2 : above;
    return { left: TIMELINE_HEADER_WIDTH + left, top, width };
  });
</script>

<div
  class="pointer-events-none absolute left-0 top-0 z-10 w-px bg-primary will-change-transform"
  style:height="{bodyHeight}px"
  style:transform="translateX({TIMELINE_HEADER_WIDTH + playheadX - 0.5}px)"
  aria-hidden="true"
></div>
{#if selected}
  <div
    class="pointer-events-none absolute z-[11] rounded-[2px] bg-white"
    style:left="{TIMELINE_HEADER_WIDTH + selected.x - selected.box.w / 2}px"
    style:top="{selected.laneTop + selected.box.y}px"
    style:width="{selected.box.w}px"
    style:height="{selected.box.h}px"
    style:box-shadow="0 0 0 2px {selected.color}, 0 0 10px {selected.color}"
    aria-hidden="true"
  ></div>
{/if}
{#if hover}
  <div
    class="pointer-events-none absolute z-[12] rounded-full"
    style:left="{TIMELINE_HEADER_WIDTH + hover.x - hover.box.w / 2}px"
    style:top="{hover.laneTop + hover.box.y}px"
    style:width="{hover.box.w}px"
    style:height="{hover.box.h}px"
    style:background={hover.color}
    style:box-shadow="0 0 0 1.5px {hover.color}66"
    aria-hidden="true"
  ></div>
{/if}
{#if tooltip && tooltipBox}
  <div
    class="pointer-events-none absolute z-50 flex h-5 items-center justify-center whitespace-nowrap rounded bg-foreground px-1.5 font-mono text-[11px] font-medium text-background shadow-sm"
    style:left="{tooltipBox.left}px"
    style:top="{tooltipBox.top}px"
    style:min-width="{tooltipBox.width}px"
    aria-hidden="true"
  >
    {tooltip.text}
  </div>
{/if}
