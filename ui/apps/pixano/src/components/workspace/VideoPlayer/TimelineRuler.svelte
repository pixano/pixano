<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // The 44 px ruler band: ticks on three levels (every frame, every few frames, major times),
  // two-line labels to the right of each major line, the playhead badge, and pointer
  // scrubbing. Not focusable: the keyboard moves the playhead with the frame shortcuts.
  import { onMount } from "svelte";

  import { getTimelineLayoutContext } from "./timelineContext";
  import { formatTimecode, frameTime } from "$lib/timeline/timeFormat";
  import {
    badgeWidthForFrame,
    frameToX,
    playheadBadgeLeft,
    xToFrame,
  } from "$lib/timeline/timelineGeometry";
  import {
    buildRulerMarks,
    chooseRulerLevels,
    DEFAULT_RULER_LABEL_METRICS,
    RULER_LABEL_OFFSET_PX,
    rulerRectPath,
    type RulerLabelMetrics,
  } from "$lib/timeline/timelineRuler";
  import { effectProbe } from "$lib/utils/effectProbe";

  interface Props {
    laneWidth: number;
    currentFrame: number;
    onSeek: (frame: number) => void;
    onScrubChange: (scrubbing: boolean) => void;
  }

  let { laneWidth, currentFrame, onSeek, onScrubChange }: Props = $props();

  const layout = getTimelineLayoutContext();
  const RULER_HEIGHT = 44;

  let metrics = $state<RulerLabelMetrics>(DEFAULT_RULER_LABEL_METRICS);
  let element = $state<HTMLDivElement>();
  let scrubPointerId: number | null = null;
  let pendingClientX: number | null = null;
  let frameRequest = 0;
  let hoverFrame = $state<number | null>(null);

  // Label widths from the real font, once it has loaded.
  onMount(() => {
    const measure = () => {
      const context = document.createElement("canvas").getContext("2d");
      if (!context) return;
      context.font = '500 11px "JetBrains Mono", monospace';
      const timeCharWidth = context.measureText("0").width;
      context.font = '400 10px "JetBrains Mono", monospace';
      const frameCharWidth = context.measureText("0").width;
      if (timeCharWidth > 0 && frameCharWidth > 0) metrics = { timeCharWidth, frameCharWidth };
    };
    measure();
    void document.fonts?.ready.then(measure);
    return () => cancelAnimationFrame(frameRequest);
  });

  const levels = $derived(
    chooseRulerLevels(layout.geometry.pxPerFrame, layout.fps, layout.geometry.lastFrame, metrics),
  );
  const marks = $derived.by(() => {
    effectProbe("Timeline.ruler");
    return buildRulerMarks(layout.geometry, layout.fps, levels, layout.frameWindow, metrics);
  });
  const x0 = $derived(layout.pxWindow.x0);
  const svgWidth = $derived(Math.max(0, layout.pxWindow.x1 - layout.pxWindow.x0));
  const shift = (xs: number[]) => xs.map((x) => x - x0);
  const minorPath = $derived(rulerRectPath(shift(marks.minor), 39, RULER_HEIGHT, layout.dpr));
  const mediumPath = $derived(rulerRectPath(shift(marks.medium), 35, RULER_HEIGHT, layout.dpr));
  const majorPath = $derived(rulerRectPath(shift(marks.major), 0, RULER_HEIGHT, layout.dpr));

  const playheadX = $derived(frameToX(layout.geometry, currentFrame));
  const badgeWidth = $derived(badgeWidthForFrame(currentFrame, metrics.timeCharWidth));
  const badgeLeft = $derived(playheadBadgeLeft(layout.geometry, currentFrame, badgeWidth));
  const hoverText = $derived(
    hoverFrame === null
      ? null
      : `#${hoverFrame} · ${formatTimecode(frameTime(hoverFrame, layout.fps))}`,
  );
  const hoverX = $derived(hoverFrame === null ? 0 : frameToX(layout.geometry, hoverFrame));

  function frameAt(clientX: number): number {
    const rect = element?.getBoundingClientRect();
    return rect ? xToFrame(layout.geometry, clientX - rect.left) : 0;
  }

  function flushScrub() {
    frameRequest = 0;
    if (pendingClientX === null) return;
    onSeek(frameAt(pendingClientX));
    pendingClientX = null;
  }

  function onPointerDown(event: PointerEvent) {
    if (event.button !== 0 || event.ctrlKey) return;
    element?.setPointerCapture(event.pointerId);
    scrubPointerId = event.pointerId;
    hoverFrame = null;
    onScrubChange(true);
    onSeek(frameAt(event.clientX));
  }

  function onPointerMove(event: PointerEvent) {
    if (scrubPointerId === event.pointerId) {
      pendingClientX = event.clientX;
      if (!frameRequest) frameRequest = requestAnimationFrame(flushScrub);
      return;
    }
    if (event.pointerType === "mouse") hoverFrame = frameAt(event.clientX);
  }

  function endScrub(event: PointerEvent) {
    if (scrubPointerId !== event.pointerId) return;
    if (frameRequest) {
      cancelAnimationFrame(frameRequest);
      flushScrub();
    }
    scrubPointerId = null;
    if (element?.hasPointerCapture(event.pointerId)) element.releasePointerCapture(event.pointerId);
    onScrubChange(false);
  }
</script>

<div
  bind:this={element}
  class="relative h-11 cursor-pointer border-b border-border bg-timeline-ruler"
  style:width="{laneWidth}px"
  style:touch-action="none"
  role="presentation"
  onpointerdown={onPointerDown}
  onpointermove={onPointerMove}
  onpointerup={endScrub}
  onpointercancel={endScrub}
  onlostpointercapture={endScrub}
  onpointerleave={() => (hoverFrame = null)}
>
  <svg
    class="pointer-events-none absolute top-0"
    style:left="{x0}px"
    width={svgWidth}
    height={RULER_HEIGHT}
    viewBox="0 0 {svgWidth} {RULER_HEIGHT}"
    aria-hidden="true"
  >
    <path d={minorPath} class="fill-muted-foreground/40" />
    <path d={mediumPath} class="fill-muted-foreground/70" />
    <path d={majorPath} class="fill-muted-foreground/70" />
  </svg>
  {#each marks.labels as label (label.frame)}
    <div
      class="pointer-events-none absolute top-[5px] flex flex-col gap-px whitespace-nowrap font-mono leading-none"
      style:left="{label.x + RULER_LABEL_OFFSET_PX}px"
      aria-hidden="true"
    >
      <span class="text-[11px] font-medium text-foreground">{label.time}</span>
      <span class="text-[10px] text-foreground/65">{label.frameText}</span>
    </div>
  {/each}

  {#if hoverText}
    <div
      class="pointer-events-none absolute inset-y-0 z-[5] w-px bg-foreground/30"
      style:left="{hoverX - 0.5}px"
      aria-hidden="true"
    ></div>
    <div
      class="pointer-events-none absolute bottom-[3px] z-[5] whitespace-nowrap rounded-[5px] border border-foreground/40 bg-timeline-ruler px-1.5 font-mono text-[10px] leading-4 text-foreground"
      style:left="{Math.min(Math.max(hoverX + 6, 2), laneWidth - 120)}px"
      aria-hidden="true"
    >
      {hoverText}
    </div>
  {/if}

  <div
    class="pointer-events-none absolute left-0 top-[22px] z-10 h-[26px] w-px bg-primary will-change-transform"
    style:transform="translateX({playheadX - 0.5}px)"
    aria-hidden="true"
  ></div>
  <div
    class="pointer-events-none absolute left-0 top-[2px] z-10 flex h-5 items-center justify-center rounded-[5px] bg-primary font-mono text-[11px] font-medium text-card shadow-[0_0_0_2px_hsl(var(--timeline-ruler))] will-change-transform"
    style:width="{badgeWidth}px"
    style:transform="translateX({badgeLeft}px)"
    aria-hidden="true"
  >
    {currentFrame}
  </div>
</div>
