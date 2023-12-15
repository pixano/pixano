<script lang="ts">
  import {
    api,
    // ConfirmModal,
    // Header,
    // Library,
    // LoadingModal,
    // PromptModal,
    // WarningModal,
  } from "@pixano/core";

  import type {
    // BBox,
    // DatasetCategory,
    DatasetInfo,
    // DatasetItem,
    // ItemLabels,
    // Mask,
  } from "@pixano/core";

  import Counter from "./Counter.svelte";
  import welcome from "$lib/images/svelte-welcome.webp";
  import welcome_fallback from "$lib/images/svelte-welcome.png";

  let models: Array<string>;
  let datasets: Array<DatasetInfo> = [];
  let loadingDatasetsModal = false;

  async function handleGetModels() {
    console.log("App.handleGetModels");

    const start = Date.now();
    models = await api.getModels();
    console.log("App.handleGetModels - api.getModels in", Date.now() - start, "ms");
  }

  async function handleGetDatasets() {
    console.log("App.handleGetDatasets");

    loadingDatasetsModal = true;

    const start = Date.now();
    const loadedDatasets = await api.getDatasets();
    console.log("App.handleGetDatasets - api.getDatasets in", Date.now() - start, "ms");

    datasets = loadedDatasets ? loadedDatasets : [];
    loadingDatasetsModal = false;
  }
</script>

<svelte:head>
  <title>Home</title>
  <meta name="description" content="Svelte demo app" />
</svelte:head>

<section>
  <h1>
    <span class="welcome">
      <picture>
        <source srcset={welcome} type="image/webp" />
        <img src={welcome_fallback} alt="Welcome" />
      </picture>
    </span>

    to your new<br />SvelteKit app
  </h1>

  <h2>
    try editing <strong>src/routes/+page.svelte</strong>
  </h2>

  <Counter />
</section>

<style>
  section {
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    flex: 0.6;
  }

  h1 {
    width: 100%;
  }

  .welcome {
    display: block;
    position: relative;
    width: 100%;
    height: 0;
    padding: 0 0 calc(100% * 495 / 2048) 0;
  }

  .welcome img {
    position: absolute;
    width: 100%;
    height: 100%;
    top: 0;
    display: block;
  }
</style>
