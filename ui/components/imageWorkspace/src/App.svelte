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
  import type { ItemData, BBox } from "@pixano/core";

  import Toolbar from "./components/Toolbar.svelte";
  import ImageCanvas from "./components/ImageCanvas.svelte";
  import ActionsTabs from "./components/ActionsTabs/ActionsTabs.svelte";
  import { mockImage } from "./lib/mock";
  import { objects } from "./lib/stores/stores";
  import "./index.css";

  export let selectedTool: tools.Tool | null;
  export let selectedItem: ItemData = mockImage;
  let bboxes: BBox[] = [];

  objects.subscribe((value) => {
    bboxes = value.reduce((acc, val) => {
      if (val.type === "box") acc.push(val.boundingBox);
      return acc;
    }, [] as BBox[]);
  });
</script>

<div class="flex w-full h-screen bg-primary relative">
  <Toolbar bind:selectedTool />
  <ImageCanvas {selectedTool} {selectedItem} bind:bboxes />
  <ActionsTabs />
</div>
