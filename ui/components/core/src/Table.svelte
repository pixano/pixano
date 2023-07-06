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

  import { createEventDispatcher } from "svelte/internal";
  import TableCell from "./TableCell.svelte";
  import type { CellData } from "./cell_types";

  export let featureNames: Array<any>;
  export let features: Array<Array<CellData>>;

  const dispatch = createEventDispatcher();

  function handleItemClick(selectedFeatures) {
    const itemId = selectedFeatures.find((col) => {
      return col.name === "id";
    });
    dispatch("itemclick", { id: itemId.value });
  }
</script>

<div
  class="h-full bg-white overflow-y-auto overflow-x-auto border rounded-lg
  dark:bg-zinc-800 dark:border-zinc-700"
>
  <table class="table-auto w-full text-sm text-left">
    <thead class="text-xs text-zinc-700 uppercase dark:text-zinc-400">
      <tr
        class="sticky p-2 top-0 bg-zinc-100 border-b-2 dark:bg-zinc-900 dark:border-zinc-700 "
      >
        {#each featureNames as { name, type }}
          {#if type != "hidden"}
            <th class="pl-2 py-1">{name}</th>
          {/if}
        {/each}
      </tr>
    </thead>
    <tbody>
      {#each features as columns}
        <tr
          class="cursor-pointer hover:bg-zinc-100 dark:hover:bg-zinc-700"
          on:click={() => {
            handleItemClick(columns);
          }}
        >
          {#each columns as col}
            {#if col.dtype != "hidden"}
              <td class="border-b dark:border-zinc-700 py-2">
                <TableCell data={col} />
              </td>
            {/if}
          {/each}
        </tr>
      {/each}
    </tbody>
  </table>
</div>
