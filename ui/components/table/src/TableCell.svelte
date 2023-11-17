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
  import HistogramCell from "./TableCells/HistogramCell.svelte";
  import ImageCell from "./TableCells/ImageCell.svelte";
  import VideoCell from "./TableCells/VideoCell.svelte";
  import NumberCell from "./TableCells/NumberCell.svelte";
  import TextCell from "./TableCells/TextCell.svelte";

  import type { DatasetItemFeature } from "@pixano/core";

  // Exports
  export let itemFeature: DatasetItemFeature;

  // Map types to cell components
  const componentsMap = {
    number: NumberCell,
    text: TextCell,
    image: ImageCell,
    video: VideoCell,
    histogram: HistogramCell,
  };
</script>

<svelte:component this={componentsMap[itemFeature.dtype]} value={itemFeature.value} />
