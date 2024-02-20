<script lang="ts">
  /**
   * @copyright CEA
   * @author CEA
   * @license CECILL
   *
   * This software is a collaborative computer program whose purpose is to
   * generate and explore labeled data for computer vision applications.
   * This software is governed by the CeCILL-C license under French law and
   * abiding by the rules of distribution of free software. You can use,
   * modify and/ or redistribute the software under the terms of the CeCILL-C
   * license as circulated by CEA, CNRS and INRIA at the following URL
   *
   * http://www.cecill.info
   */

  // Imports
  import { Bar } from "svelte-chartjs";
  import {
    Chart,
    Title,
    Tooltip,
    Legend,
    BarElement,
    CategoryScale,
    LinearScale,
    type ChartDataset,
  } from "chart.js";
  import zoomPlugin from "chartjs-plugin-zoom";
  import type { DatasetStat } from "..";
  import { colors } from "./colors";

  // Define props
  export let hist: DatasetStat;

  // Separate splits
  let splits: string[] = [...new Set(hist.histogram.map((item) => String(item.split)))];
  let chartDatasets: ChartDataset[] = splits.map((split, i) => ({
    label: split,
    backgroundColor: colors[i] + "40",
    borderColor: colors[i],
    borderWidth: 2,
    data: hist.histogram.filter((item) => item.split === split).map((item) => item.counts),
  }));

  // Define label names
  let labels;
  if (hist.type == "numerical")
    labels = [...new Set(hist.histogram.map((item) => item.bin_start + "-" + item.bin_end))];
  else if (hist.type == "categorical")
    labels = [...new Set(hist.histogram.map((item) => item[hist.name]))];

  // Prepare chart data and options
  let data = {
    labels,
    datasets: chartDatasets,
  };
  let options = {
    maintainAspectRatio: false,
    plugins: {
      title: {
        display: true,
        text: hist.name,
      },
      zoom: {
        zoom: {
          wheel: {
            enabled: true,
            speed: 0.05,
          },
          mode: "x",
        },
        pan: {
          enabled: true,
          mode: "x",
        },
      },
    },
    responsive: true,
    scales: {
      x: { stacked: true },
      y: { stacked: true },
    },
  };

  Chart.register(Title, Tooltip, Legend, BarElement, CategoryScale, LinearScale, zoomPlugin);
</script>

<!-- Histogram -->
<Bar {data} {options} />
