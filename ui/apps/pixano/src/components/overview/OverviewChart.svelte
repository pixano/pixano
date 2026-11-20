<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script module lang="ts">
  import {
    BarController,
    BarElement,
    CategoryScale,
    Chart,
    Legend,
    LinearScale,
    Tooltip,
  } from "chart.js";

  // Once for every chart of the page.
  Chart.register(BarController, BarElement, CategoryScale, LinearScale, Tooltip, Legend);
</script>

<script lang="ts">
  import type { ActiveElement, ChartData, ChartEvent, ChartOptions, LegendItem } from "chart.js";
  import { untrack } from "svelte";

  import { themeMode } from "$lib/stores/appStores.svelte";
  import { formatShare, PERCENT, type ChartSeries } from "$lib/utils/overview";
  import { readTokens, tokenColor } from "$lib/utils/themeColors";

  type Props = {
    labels: string[];
    series: ChartSeries[];
    /** Whether the series are shares, from 0 to 1, rather than counts. */
    shares: boolean;
    /** Per bar, whether to point it out. */
    notable: boolean[];
    /** Per bar, whether clicking it filters the records. */
    clickable: boolean[];
    /** Per bar, whether the filters of the card's own column keep some of its records. */
    selected: boolean[];
    /** Whether the card's own column is filtered: the bars its filters keep stand out. */
    filtered: boolean;
    /** Bars side by side along a vertical axis of labels: for values, whose labels are words. */
    horizontal: boolean;
    /** What the chart shows, for those who do not see it. */
    description: string;
    /** A bar that filters the records was clicked: its index. */
    onBarClick?: (index: number) => void;
  };
  let {
    labels,
    series,
    shares,
    notable,
    clickable,
    selected,
    filtered,
    horizontal,
    description,
    onBarClick,
  }: Props = $props();

  /** The theme's tokens the splits' bars take, in the order of the overview's splits. */
  const SERIES_TOKENS = ["--primary", "--info", "--success", "--warning", "--muted-foreground"];
  /** The tokens of a bar pointed out, of the grid, and of the axes' text. */
  const OTHER_TOKENS = ["--destructive", "--border", "--muted-foreground"];
  /** How opaque a bar's fill is; a bar the card's own filters leave out is faded. */
  const FILL_ALPHA = 0.7;
  const FADED_ALPHA = 0.2;
  const NOTABLE_BORDER_WIDTH = 2;
  const BORDER_WIDTH = 1;
  const BAR_RADIUS = 3;
  /** The height of a horizontal chart's bar, in pixels, so that each label reads. */
  const ROW_HEIGHT = 18;
  const MIN_HORIZONTAL_HEIGHT = 120;
  /** The tallest a horizontal chart shows at once: past it, it scrolls within its card. */
  const MAX_VISIBLE_HEIGHT = 480;
  /** The longest an axis writes a value, in characters: the tooltip writes it whole. */
  const MAX_TICK_LABEL_LENGTH = 24;
  const ELLIPSIS = "…";
  /** The decimals of the value axis' ticks: shares to the hundredth, counts whole. */
  const SHARE_TICK_PRECISION = 2;
  const COUNT_TICK_PRECISION = 0;
  const TICK_FONT_SIZE = 10;
  const LEGEND_FONT_SIZE = 11;
  const LEGEND_BOX_WIDTH = 10;
  const MAX_TICK_ROTATION = 50;

  type Palette = { series: string[]; notable: string; grid: string; text: string };

  function readPalette(): Palette {
    const seriesColors = readTokens(SERIES_TOKENS);
    const [notableColor, grid, text] = readTokens(OTHER_TOKENS);
    return { series: seriesColors, notable: notableColor, grid, text };
  }

  function samePalette(one: Palette, other: Palette): boolean {
    return (
      one.notable === other.notable &&
      one.grid === other.grid &&
      one.text === other.text &&
      one.series.every((color, index) => color === other.series[index])
    );
  }

  let palette = $state<Palette>(readPalette());
  // The theme puts its class on the page in an effect of its own: its colors are read once it has,
  // and the chart drawn again only when they changed.
  $effect(() => {
    void themeMode.value;
    const frame = requestAnimationFrame(() => {
      const read = readPalette();
      if (!samePalette(read, palette)) palette = read;
    });
    return () => cancelAnimationFrame(frame);
  });

  function seriesColor(colorIndex: number): string {
    return palette.series[colorIndex % palette.series.length];
  }

  function tickLabel(label: string): string {
    return label.length > MAX_TICK_LABEL_LENGTH
      ? `${label.slice(0, MAX_TICK_LABEL_LENGTH - 1)}${ELLIPSIS}`
      : label;
  }

  const data = $derived<ChartData<"bar", number[], string>>({
    labels: labels.map(tickLabel),
    datasets: series.map((one) => {
      const color = seriesColor(one.colorIndex);
      return {
        label: one.label,
        data: one.values,
        backgroundColor: labels.map((_label, index) =>
          tokenColor(color, filtered && !selected[index] ? FADED_ALPHA : FILL_ALPHA),
        ),
        // A bar its filter leaves out keeps no full outline, but one pointed out keeps its own.
        borderColor: notable.map((pointed, index) =>
          pointed
            ? tokenColor(palette.notable)
            : tokenColor(color, filtered && !selected[index] ? FADED_ALPHA : 1),
        ),
        borderWidth: notable.map((pointed) => (pointed ? NOTABLE_BORDER_WIDTH : BORDER_WIDTH)),
        borderRadius: BAR_RADIUS,
      };
    }),
  });

  /** The bar the pointer is over: every split's bar of a row answers with that row's index. */
  function barUnder(elements: ActiveElement[]): number | null {
    return elements.length > 0 ? elements[0].index : null;
  }

  function formatTick(value: number | string): string {
    const number = Number(value);
    return shares ? `${Math.round(number * PERCENT)}%` : number.toLocaleString();
  }

  const options = $derived<ChartOptions<"bar">>({
    indexAxis: horizontal ? "y" : "x",
    maintainAspectRatio: false,
    animation: false,
    // A bar's whole row answers the pointer, whichever split's bar is under it, and a thin one too.
    interaction: { mode: "index", intersect: false, axis: horizontal ? "y" : "x" },
    plugins: {
      legend: {
        display: series.length > 1,
        position: "bottom",
        labels: {
          boxWidth: LEGEND_BOX_WIDTH,
          color: tokenColor(palette.text),
          font: { size: LEGEND_FONT_SIZE },
          // A split's own color: the outline of a bar pointed out is not the split's.
          generateLabels: (shown: Chart): LegendItem[] =>
            series.map((one, index) => ({
              text: one.label,
              fillStyle: tokenColor(seriesColor(one.colorIndex), FILL_ALPHA),
              strokeStyle: tokenColor(seriesColor(one.colorIndex)),
              fontColor: tokenColor(palette.text),
              lineWidth: BORDER_WIDTH,
              hidden: !shown.isDatasetVisible(index),
              datasetIndex: index,
            })),
        },
      },
      tooltip: {
        callbacks: {
          title: (items) => (items.length > 0 ? (labels[items[0].dataIndex] ?? "") : ""),
          label: (context) => {
            const prefix = context.dataset.label ? `${context.dataset.label}: ` : "";
            const value = Number(horizontal ? context.parsed.x : context.parsed.y);
            return `${prefix}${shares ? formatShare(value) : value.toLocaleString()}`;
          },
        },
      },
    },
    scales: {
      [horizontal ? "y" : "x"]: {
        grid: { display: false },
        ticks: {
          color: tokenColor(palette.text),
          font: { size: TICK_FONT_SIZE },
          maxRotation: MAX_TICK_ROTATION,
          autoSkip: !horizontal,
        },
      },
      [horizontal ? "x" : "y"]: {
        beginAtZero: true,
        grid: { color: tokenColor(palette.grid) },
        ticks: {
          color: tokenColor(palette.text),
          precision: shares ? SHARE_TICK_PRECISION : COUNT_TICK_PRECISION,
          font: { size: TICK_FONT_SIZE },
          callback: formatTick,
        },
      },
    },
    onClick: (_event: ChartEvent, elements: ActiveElement[]) => {
      const index = barUnder(elements);
      if (index !== null && clickable[index]) onBarClick?.(index);
    },
    onHover: (event: ChartEvent, elements: ActiveElement[]) => {
      const target = event.native?.target as HTMLElement | undefined;
      const index = barUnder(elements);
      const pointing = onBarClick !== undefined && index !== null && clickable[index];
      if (target) target.style.cursor = pointing ? "pointer" : "default";
    },
  });

  const height = $derived(
    horizontal ? Math.max(MIN_HORIZONTAL_HEIGHT, labels.length * ROW_HEIGHT * series.length) : null,
  );

  let canvas = $state<HTMLCanvasElement | null>(null);
  let chart: Chart<"bar", number[], string> | null = null;

  $effect(() => {
    if (!canvas) return;
    const element = canvas;
    const created = untrack(() => new Chart(element, { type: "bar", data, options }));
    chart = created;
    return () => {
      created.destroy();
      chart = null;
    };
  });

  // The datasets are updated in place: chart.js keeps a split hidden from its legend by the dataset
  // object, which a new one would show again.
  $effect(() => {
    const nextData = data;
    const nextOptions = options;
    if (!chart) return;
    chart.data.labels = nextData.labels;
    nextData.datasets.forEach((dataset, index) => {
      const current = chart?.data.datasets[index];
      if (current) Object.assign(current, dataset);
      else chart?.data.datasets.push(dataset);
    });
    chart.data.datasets.length = nextData.datasets.length;
    chart.options = nextOptions;
    chart.update();
  });
</script>

<div
  class="overflow-y-auto"
  style={height === null ? undefined : `max-height: ${MAX_VISIBLE_HEIGHT}px`}
>
  <div
    class="relative {height === null ? 'h-48' : ''}"
    style={height === null ? undefined : `height: ${height}px`}
    role="img"
    aria-label={description}
  >
    <canvas bind:this={canvas}></canvas>
  </div>
</div>
