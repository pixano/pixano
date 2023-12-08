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

  import { newShape, colorRange } from "../lib/stores/stores";

  export let selectedItem: DatasetItem;
  export let masks: Array<Mask> = [];
  export let bboxes: Array<BBox> = [];
  export let embeddings: Record<string, ort.Tensor>;

  export let selectedTool: SelectionTool;
  export let currentAnn: InteractiveImageSegmenterOutput | null = null;

  let colorRangeValue: string[] = [];

  colorRange.subscribe((value) => (colorRangeValue = value));
</script>

<div class="flex-auto max-w-[70%]">
  <Canvas2D
    {selectedItem}
    colorRange={colorRangeValue}
    bind:masks
    bind:bboxes
    {embeddings}
    bind:selectedTool
    bind:currentAnn
    createNewShape={(shape) => newShape.set(shape)}
  />
</div>
