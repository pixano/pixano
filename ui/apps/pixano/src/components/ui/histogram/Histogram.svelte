<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import {
    BarElement,
    CategoryScale,
    Chart,
    Legend,
    LinearScale,
    Title,
    Tooltip,
    type ChartData,
    type ChartDataset,
    type ChartOptions,
  } from "chart.js";
  import zoomPlugin from "chartjs-plugin-zoom";
  import { untrack } from "svelte";

  import type { DatasetStat } from "$lib/types/dataset";
  import { colors } from "./colors";

  
  interface Props {
    // Define props
    hist: DatasetStat;
    minimal?: boolean; // Hides title, y-axis label, legend, and other elements
  }

  let { hist, minimal = false }: Props = $props();

  const splits = $derived.by(() => [...new Set(hist.histogram.map((item) => String(item.split)))]);
  const chartDatasets = $derived.by<ChartDataset<"bar", number[]>[]>(() =>
    splits.map((split, i) => ({
      label: split,
      backgroundColor: colors[i] + "40",
      borderColor: colors[i],
      borderWidth: 2,
      data: hist.histogram
        .filter((item) => item.split === split)
        .map((item) => Number(item.counts)),
    })),
  );

  const labels = $derived.by(() => {
    if (hist.type === "numerical") {
      return [...new Set(hist.histogram.map((item) => `${item.bin_start}-${item.bin_end}`))];
    }
    if (hist.type === "categorical") {
      return [...new Set(hist.histogram.map((item) => String(item[hist.name])))];
    }
    return [];
  });

  const data = $derived.by<ChartData<"bar", number[], string>>(() => ({
    labels,
    datasets: chartDatasets,
  }));

  const options = $derived.by<ChartOptions<"bar">>(() => ({
    maintainAspectRatio: false,
    plugins: {
      title: {
        display: !minimal,
        text: hist.name,
      },
      legend: { display: !minimal },
      zoom: {
        zoom: {
          wheel: {
            enabled: true,
            speed: 0.05,
          },
          mode: "x" as const,
        },
        pan: {
          enabled: true,
          mode: "x" as const,
        },
      },
    },

    responsive: true,
    scales: {
      x: {
        stacked: true,
        grid: { display: !minimal },
        ticks: { font: { size: minimal ? 10 : 12 } },
      },
      y: {
        stacked: true,
        grid: { display: !minimal },
        ticks: { font: { size: minimal ? 10 : 12 } },
      },
    },
  }));

  Chart.register(Title, Tooltip, Legend, BarElement, CategoryScale, LinearScale, zoomPlugin);

  let canvasElement = $state<HTMLCanvasElement | null>(null);
  let chart = $state<Chart<"bar", number[], string> | null>(null);

  $effect(() => {
    if (!canvasElement) return;
    const c = untrack(() => new Chart(canvasElement, {
      type: "bar",
      data,
      options,
    }));
    chart = c;
    return () => {
      c.destroy();
      chart = null;
    };
  });

  $effect(() => {
    if (!chart) return;
    chart.data = data;
    chart.options = options;
    chart.update();
  });
</script>

<!-- Histogram -->
<canvas bind:this={canvasElement}></canvas>
