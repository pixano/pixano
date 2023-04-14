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
  import NumberCell from "./TableCells/NumberCell.svelte";
  import TextCell from "./TableCells/TextCell.svelte";
  import ImageCell from "./TableCells/ImageCell.svelte";
  import HistogramCell from "./TableCells/HistogramCell.svelte";
  import type { CellData } from "./cell_types";

  export let data: CellData;

  // Map types to cell components
  const componentsMap = {
    number: NumberCell,
    text: TextCell,
    image: ImageCell,
    histogram: HistogramCell,
  };
</script>

<svelte:component this={componentsMap[data.dtype]} value={data.value} />
