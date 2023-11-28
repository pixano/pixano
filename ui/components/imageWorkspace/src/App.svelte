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
  import { tools } from "@pixano/canvas2d";
  import type { ItemData } from "@pixano/core";

  import Toolbar from "./components/Toolbar.svelte";
  import ImageCanvas from "./components/ImageCanvas.svelte";
  import ActionsTabs from "./components/ActionsTabs/ActionsTabs.svelte";
  import { mockImage } from "./lib/mock";
  import "./index.css";

  export let selectedTool: tools.Tool | null;
  export let selectedItem: ItemData = mockImage;
</script>

<div class="flex w-full h-screen bg-primary">
  <Toolbar bind:selectedTool />
  <ImageCanvas {selectedTool} {selectedItem} />
  <ActionsTabs />
</div>
