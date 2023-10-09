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
  import { createEventDispatcher } from "svelte/internal";

  import TableCell from "./TableCell.svelte";

  import type { Dataset, DatasetItem } from "./interfaces";

  // Exports
  export let selectedDataset: Dataset;

  const featureNames = selectedDataset.page.items[0].map((feature) => {
    return { name: feature.name, type: feature.dtype };
  });

  const dispatch = createEventDispatcher();

  function handleSelectItem(item: DatasetItem) {
    const itemId = item.find((feature) => {
      return feature.name === "id";
    }).value;
    dispatch("selectItem", itemId);
  }
</script>

<div
  class="h-full overflow-y-auto overflow-x-auto border rounded-lg
  bg-white dark:bg-zinc-800 shadow
  text-zinc-500 dark:text-zinc-300
  border-zinc-300 dark:border-zinc-600"
>
  <table class="table-auto z-0 w-full text-sm text-left">
    <thead class="uppercase">
      <tr
        class="sticky top-0 bg-white dark:bg-zinc-700 shadow-md"
      >
        {#each featureNames as { name, type }}
          {#if type != "hidden"}
            <th class="pl-2 py-3 text-rose-400 font-semibold">{name}</th>
          {/if}
        {/each}
      </tr>
    </thead>
    <tbody>
      {#each selectedDataset.page.items as item}
        <tr
          class="cursor-pointer hover:bg-zinc-100 dark:hover:bg-zinc-700"
          on:click={() => {
            handleSelectItem(item);
          }}
        >
          {#each item as itemFeature}
            {#if itemFeature.dtype != "hidden"}
              <td class="border-b py-2 border-zinc-300 dark:border-zinc-600">
                <TableCell {itemFeature} />
              </td>
            {/if}
          {/each}
        </tr>
      {/each}
    </tbody>
  </table>
</div>
