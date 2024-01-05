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
  import { VegaLite, type VisualizationSpec } from "svelte-vega";

  import type { DatasetStat } from "../lib/types/datasetTypes";

  // Exports
  export let hist: DatasetStat;
  export let maxHeight = 48;
  export let hideTitle = false;

  // Calculate histogram height
  let h = 7.5 * hist.histogram.length;
  h = h < 125 ? 125 : h;

  // Vega-Lite spec
  const spec: VisualizationSpec = {
    $schema: "https://vega.github.io/schema/vega-lite/v5.json",
    config: {
      style: {
        cell: {
          stroke: "transparent",
        },
      },
    },
    params: [
      {
        name: "highlight",
        select: {
          type: "point",
          on: "mouseover",
        },
      },
    ],
    data: {
      values: hist.histogram,
    },
    height: h,
    width: 150,
    background: "transparent",
    mark: { type: "bar", tooltip: true },
    encoding: {
      x: {
        field: "counts",
        type: "quantitative",
        axis: {
          title: null,
          grid: false,
          domain: false,
          ticks: false,
          labels: false,
        },
      },
      y: {
        field: hist.type == "categorical" ? hist.name : "bin_range",
        type: "nominal",
        sort: "x",
        axis: {
          title: null,
          domain: false,
          grid: false,
          ticks: false,
          labelLimit: 50,
          labelPadding: 10,
        },
      },
      color: {
        condition: [
          {
            param: "highlight",
            empty: false,
            value: "grey",
          },
        ],
        field: "split",
      },
    },
  };

  if (hist.type == "numerical") {
    // Set bin ranges
    for (let i = 0; i < hist.histogram.length; ++i) {
      const value = hist.histogram[i];
      value.bin_range = value.bin_start + "-" + value.bin_end;
    }
  }

  // Vega-lite chart options
  const options = {
    actions: false,
  };
</script>

<!-- Histogram -->
<div class="max-h-{maxHeight} w-72 mx-auto flex flex-col justify-center items-center">
  {#if !hideTitle}
    <span class="py-1 text-sm font-bold">
      {hist.name}
    </span>
  {/if}
  <div class="place-items-center overflow-y-scroll">
    <VegaLite {spec} {options} />
  </div>
</div>
