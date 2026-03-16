<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { interpolatePlasma, scaleLinear } from "d3";

  import { lastFrameIndex, playbackState, timelineZoom } from "$lib/stores/videoStores.svelte";
  import { BaseSchema, type Entity, type Tracklet } from "$lib/ui";
  import { getCurrentImageTime } from "$lib/utils/videoUtils";

  interface Props {
    entities: Entity[];
    onFrameClick: (frameIndex: number) => void;
  }

  let { entities, onFrameClick }: Props = $props();

  let surfaceElement: HTMLButtonElement = $state();
  let surfaceWidth = $state(0);
  let hoveredFrameIndex = $state<number | null>(null);

  const totalFrames = $derived(Math.max((lastFrameIndex.value ?? 0) + 1, 1));
  const totalDurationMs = $derived(Math.max(totalFrames * playbackState.value.videoSpeed, 1));
  const densityBucketCount = $derived(Math.max(48, Math.min(totalFrames, 180)));
  const densityBuckets = $derived.by(() => {
    const buckets = Array.from({ length: densityBucketCount }, () => 0);
    const bucketSize = totalFrames / densityBucketCount;

    for (const entity of entities) {
      for (const child of entity.ui.childs ?? []) {
        if (!child.is_type(BaseSchema.Tracklet)) continue;
        const tracklet = child as Tracklet;
        const startBucket = Math.max(0, Math.floor(tracklet.data.start_frame / bucketSize));
        const endBucket = Math.min(
          densityBucketCount - 1,
          Math.floor(tracklet.data.end_frame / bucketSize),
        );

        for (let bucketIndex = startBucket; bucketIndex <= endBucket; bucketIndex += 1) {
          buckets[bucketIndex] += 1;
        }
      }
    }

    const smoothedBuckets = buckets.map((_, index) => {
      let weightedSum = 0;
      let totalWeight = 0;

      for (let offset = -2; offset <= 2; offset += 1) {
        const neighborIndex = index + offset;
        if (neighborIndex < 0 || neighborIndex >= buckets.length) continue;
        const weight = 3 - Math.abs(offset);
        weightedSum += buckets[neighborIndex] * weight;
        totalWeight += weight;
      }

      return totalWeight > 0 ? weightedSum / totalWeight : 0;
    });

    const maxCount = Math.max(...smoothedBuckets, 0);
    const colorScale = scaleLinear<number, number>()
      .domain([0, Math.max(maxCount, 1)])
      .range([0.08, 0.98])
      .clamp(true);

    return buckets.map((count, index) => ({
      index,
      count,
      smoothedCount: smoothedBuckets[index],
      normalized: colorScale(smoothedBuckets[index]),
      color: interpolatePlasma(colorScale(smoothedBuckets[index])),
    }));
  });

  const tickStepSeconds = $derived.by(() => {
    const pixelsPerFrame = surfaceWidth > 0 ? surfaceWidth / totalFrames : 0;

    if (pixelsPerFrame < 0.25) return 30;
    if (pixelsPerFrame < 0.5) return 15;
    if (pixelsPerFrame < 1.2) return 10;
    if (pixelsPerFrame < 3) return 5;
    if (pixelsPerFrame < 6) return 2;
    return 1;
  });

  const ticks = $derived.by(() => {
    const marks: Array<{ second: number; leftPct: number; label: string }> = [];
    const totalSeconds = Math.max(1, Math.ceil(totalDurationMs / 1000));

    for (let second = 0; second <= totalSeconds; second += tickStepSeconds) {
      marks.push({
        second,
        leftPct: ((second * 1000) / totalDurationMs) * 100,
        label: getCurrentImageTime(
          Math.floor((second * 1000) / playbackState.value.videoSpeed),
          playbackState.value.videoSpeed,
        ).slice(0, 5),
      });
    }

    return marks;
  });
  const hoveredBucketIndex = $derived(
    hoveredFrameIndex === null
      ? null
      : Math.min(
          densityBucketCount - 1,
          Math.floor((hoveredFrameIndex / totalFrames) * densityBucketCount),
        ),
  );
  const hoveredBucket = $derived(
    hoveredBucketIndex === null ? null : densityBuckets[hoveredBucketIndex],
  );
  const hoveredTimeLabel = $derived(
    hoveredFrameIndex === null
      ? null
      : getCurrentImageTime(hoveredFrameIndex, playbackState.value.videoSpeed),
  );

  function getFrameFromClientX(clientX: number): number {
    if (!surfaceElement) return 0;
    const rect = surfaceElement.getBoundingClientRect();
    const x = Math.max(0, Math.min(clientX - rect.left, rect.width));
    const ratio = x / Math.max(rect.width, 1);
    return Math.min(totalFrames - 1, Math.max(0, Math.round(ratio * (totalFrames - 1))));
  }

  $effect(() => {
    timelineZoom.value[0];
    if (!surfaceElement) return;

    surfaceWidth = surfaceElement.getBoundingClientRect().width;
    const observer = new ResizeObserver(() => {
      surfaceWidth = surfaceElement?.getBoundingClientRect().width ?? 0;
    });

    observer.observe(surfaceElement);
    return () => observer.disconnect();
  });

  const dragMe = (node: HTMLButtonElement) => {
    let moving = false;
    let dragged = false;

    node.addEventListener("mousedown", (event) => {
      moving = true;
      dragged = false;
      const initialFrame = getFrameFromClientX(event.clientX);
      hoveredFrameIndex = initialFrame;
      onFrameClick(initialFrame);

      const dragController = new AbortController();

      window.addEventListener(
        "mousemove",
        (event) => {
          if (!moving) return;
          dragged = true;
          const frameIndex = getFrameFromClientX(event.clientX);
          hoveredFrameIndex = frameIndex;
          onFrameClick(frameIndex);
        },
        { signal: dragController.signal },
      );

      window.addEventListener(
        "mouseup",
        () => {
          moving = false;
          if (!dragged) {
            hoveredFrameIndex = initialFrame;
          }
          dragController.abort();
        },
        { signal: dragController.signal },
      );
    });
  };

  function handleClick(event: MouseEvent) {
    const frameIndex = getFrameFromClientX(event.clientX);
    hoveredFrameIndex = frameIndex;
    onFrameClick(frameIndex);
  }

  function handlePointerMove(event: MouseEvent) {
    hoveredFrameIndex = getFrameFromClientX(event.clientX);
  }
</script>

<button
  type="button"
  class="relative block h-7 w-full cursor-pointer select-none overflow-hidden rounded-md border border-border/35 bg-background/80 text-left"
  onclick={handleClick}
  onmousemove={handlePointerMove}
  onmouseleave={() => {
    hoveredFrameIndex = null;
  }}
  use:dragMe
  bind:this={surfaceElement}
>
  <div class="absolute inset-0">
    <div
      class="absolute inset-0 bg-[linear-gradient(180deg,hsl(var(--background)/0.82)_0%,hsl(var(--background)/0.58)_44%,hsl(var(--background)/0.26)_100%)] backdrop-blur-[10px]"
    ></div>
    <div
      class="absolute inset-x-0 bottom-0 h-[42%] bg-[linear-gradient(180deg,transparent_0%,hsl(var(--background)/0.06)_48%,hsl(var(--background)/0.14)_100%)]"
    ></div>
  </div>

  <div class="absolute inset-0 border-b border-border/35">
    <div class="absolute inset-x-0 bottom-0 h-px bg-border/80"></div>
    <div class="absolute inset-x-0 bottom-[6px] h-px bg-border/40"></div>
    {#each ticks as tick (tick.second)}
      <span
        class="pointer-events-none absolute bottom-0 h-2.5 w-px bg-foreground/48"
        style={`left: ${tick.leftPct}%`}
      ></span>
      {#if tick.second > 0}
        <span
          class="pointer-events-none absolute top-1 -translate-x-1/2 text-[10px] font-semibold text-foreground [text-shadow:0_1px_0_hsl(var(--background)/0.78),0_0_12px_hsl(var(--background)/0.35)]"
          style={`left: ${tick.leftPct}%`}
        >
          {tick.label}
        </span>
      {/if}
    {/each}
  </div>

  <div class="pointer-events-none absolute inset-x-0 bottom-[1px] h-[8px] overflow-hidden">
    <svg class="h-full w-full" preserveAspectRatio="none" aria-hidden="true">
      {#each densityBuckets as bucket (bucket.index)}
        <rect
          x={`${(bucket.index / densityBucketCount) * 100}%`}
          y={`${100 - Math.max(54, bucket.normalized * 100)}%`}
          width={`${100 / densityBucketCount}%`}
          height={`${Math.max(54, bucket.normalized * 100)}%`}
          rx="0.4"
          fill={bucket.color}
          opacity={0.98}
        ></rect>
      {/each}
    </svg>
  </div>

  {#if hoveredFrameIndex !== null && hoveredTimeLabel}
    <div
      class="pointer-events-none absolute inset-y-[3px] z-20 -translate-x-1/2 rounded-sm border border-border/40 bg-background/82 px-1.5 py-0.5 text-[9px] font-medium text-foreground shadow-sm backdrop-blur-md"
      style={`left: ${(hoveredFrameIndex / Math.max(totalFrames - 1, 1)) * 100}%`}
    >
      <span class="tabular-nums">{hoveredTimeLabel.slice(0, 8)}</span>
      <span class="ml-1 text-muted-foreground">#{hoveredFrameIndex}</span>
      {#if hoveredBucket && hoveredBucket.count > 0}
        <span class="ml-1 text-primary">{hoveredBucket.count}</span>
      {/if}
    </div>
  {/if}
</button>
