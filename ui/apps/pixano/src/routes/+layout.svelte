<script lang="ts">
  import type { DatasetInfo, DatasetItem } from "@pixano/core";
  import Header from "../components/Header.svelte";
  import "./styles.css";

  let selectedDataset: DatasetInfo | undefined;
  let selectedItem: DatasetItem = {
    id: "string",
    split: "string",
    views: {},
    objects: {},
    features: {},
    embeddings: {},
  };
  let saveFlag: boolean = false;

  function handleUnselectDataset() {
    selectedDataset = undefined;
  }

  function handleUnselectItem() {
    selectedItem = {
      id: "string",
      split: "string",
      views: {},
      objects: {},
      features: {},
      embeddings: {},
    };
  }

  function handleSaveItem() {
    saveFlag = !saveFlag;
  }
</script>

<div class="app">
  <Header
    app="Annotator"
    selectedTab={undefined}
    bind:selectedDataset
    bind:selectedItem
    {saveFlag}
    on:unselectDataset={handleUnselectDataset}
    on:unselectItem={handleUnselectItem}
    on:saveItem={handleSaveItem}
  />
  <main>
    <slot />
  </main>

  <footer>
    <p>visit <a href="https://kit.svelte.dev">kit.svelte.dev</a> to learn SvelteKit</p>
  </footer>
</div>

<style>
  .app {
    display: flex;
    flex-direction: column;
    min-height: 100vh;
  }

  main {
    flex: 1;
    display: flex;
    flex-direction: column;
    padding: 1rem;
    width: 100%;
    max-width: 64rem;
    margin: 0 auto;
    box-sizing: border-box;
  }

  footer {
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    padding: 12px;
  }

  footer a {
    font-weight: bold;
  }

  @media (min-width: 480px) {
    footer {
      padding: 12px 0;
    }
  }
</style>
