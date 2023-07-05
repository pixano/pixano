<script lang="ts">
  /**
  @copyright CEA-LIST/DIASI/SIALV/LVA (2023)
  @author CEA-LIST/DIASI/SIALV/LVA <pixano@cea.fr>
  @license CECILL-C

  This software is a collaborative computer program whose purpose is to
  generate and explore labeled data for computer vision applications.
  This software is governed by the CeCILL-C license under French law and
  abiding by the rules of distribution of free software. You can use, 
  modify and/ or redistribute the software under the terms of the CeCILL-C
  license as circulated by CEA, CNRS and INRIA at the following URL

  http://www.cecill.info
  */

  // Imports
  import { VegaLite, type VisualizationSpec } from "svelte-vega";

  // Exports
  export let hist;

  // Calculate histogram height
  let h = 10 * hist.histogram.length;
  h = h < 175 ? 175 : h;

  // Vega-Lite spec (default type : categorical)
  let spec: VisualizationSpec = {
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
        field: hist.name,
        type: "nominal",
        sort: "-x",
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

  // Change spec depending on histogram type
  if (hist.type == "numerical") {
    // Set bin ranges
    for (let i = 0; i < hist.histogram.length; ++i) {
      let value = hist.histogram[i];
      value.bin_range = value.bin_start + "-" + value.bin_end;
    }

    // Set histogram y axis
    spec.encoding.y.field = "bin_range";
    spec.encoding.y.sort = null;
  }

  // Vega-lite chart options
  const options = {
    actions: false,
  };
</script>

<!-- Histogram -->
<div
  class="h-full w-full flex flex-col justify-center items-center border rounded-lg bg-zinc-100"
>
  <span class="py-1 text-sm font-bold text-zinc-900">
    {hist.name}
  </span>
  <div class="max-h-48 w-full place-items-center overflow-y-scroll">
    <VegaLite {spec} {options} />
  </div>
</div>
