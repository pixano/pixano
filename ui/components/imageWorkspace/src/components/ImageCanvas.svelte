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
  import { Canvas2D, tools } from "@pixano/canvas2d";
  import type { InteractiveImageSegmenterOutput } from "@pixano/models";

  import type { BBox, ItemData, Mask } from "@pixano/core";

  export let selectedItem: ItemData;
  export let masks: Array<Mask> = [];
  export let bboxes: Array<BBox> = [];
  export let embeddings = { view: [] };
  export let colorScale = (value: string) => {
    console.log("temp function, TODO100", value);
    return "red";
  };
  export let selectedTool: tools.Tool | null;
  export let currentAnn: InteractiveImageSegmenterOutput | null = null;
</script>

<div class="flex-auto max-w-[70%]">
  <Canvas2D
    {selectedItem}
    {colorScale}
    {masks}
    {bboxes}
    {embeddings}
    bind:selectedTool
    bind:currentAnn
  />
</div>
