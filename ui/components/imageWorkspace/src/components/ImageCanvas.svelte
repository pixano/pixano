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
  import * as ort from "onnxruntime-web";
  import { Canvas2D } from "@pixano/canvas2d";
  import type { InteractiveImageSegmenterOutput } from "@pixano/models";

  import type { BBox, DatasetItem, Mask, SelectionTool } from "@pixano/core";

  import { newShape } from "../lib/stores/stores";
  // import { utils } from "@pixano/core";

  export let selectedItem: DatasetItem;
  export let masks: Array<Mask> = [];
  export let bboxes: Array<BBox> = [];
  let embeddings: Record<string, ort.Tensor> = {};

  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  export let colorScale = (value: string) => {
    // console.log("temp function, TODO100", value);
    return "#999";
  };
  export let selectedTool: SelectionTool;
  export let currentAnn: InteractiveImageSegmenterOutput | null = null;

  // let colorMode = "category";

  // export function handleLabelColors() {
  //   let range: Array<number>;
  //   if (colorMode === "category") {
  //     range = [
  //       Math.min(...classes.map((cat) => cat.id)),
  //       Math.max(...classes.map((cat) => cat.id)),
  //     ];
  //   } else if (colorMode === "source") {
  //     range = [0, Object.keys(annotations).length];
  //   } else {
  //     range = [];
  //   }
  //   return utils.ordinalColorScale(range.map((i) => i.toString())) as (id: string) => string;
  // }
</script>

<div class="flex-auto max-w-[70%]">
  <Canvas2D
    {selectedItem}
    {colorScale}
    bind:masks
    bind:bboxes
    {embeddings}
    bind:selectedTool
    bind:currentAnn
    createNewShape={(shape) => newShape.set(shape)}
  />
</div>
