<script lang="ts">
  // Imports
  import { Bar } from "svelte-chartjs";
  import { Chart, Title, Tooltip, Legend, BarElement, CategoryScale, LinearScale } from "chart.js";
  import zoomPlugin from "chartjs-plugin-zoom";

  // Define props
  export let hist: any;

  // Color palette for stacked charts
  const colors = ["#771E5F", "#1E7736", "#1E5F77", "#77361E"];

  // Separate splits
  let splits = [...new Set(hist.histogram.map((item: any) => item.split))];
  let datasets = [];
  for (let i = 0; i < splits.length; ++i) {
    datasets.push({
      label: splits[i],
      backgroundColor: colors[i] + "40",
      borderColor: colors[i],
      borderWidth: 2,
      data: hist.histogram
        .filter((item: any) => item.split === splits[i])
        .map((item: any) => item.counts),
    });
  }

  // Define label names
  let labels;
  if (hist.type == "numerical")
    labels = [...new Set(hist.histogram.map((item: any) => item.bin_start + "-" + item.bin_end))];
  else if (hist.type == "categorical")
    labels = [...new Set(hist.histogram.map((item: any) => item[hist.name]))];

  // Prepare chart data and options
  let data: any = {
    labels: labels,
    datasets: datasets,
  };
  let options: any = {
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
