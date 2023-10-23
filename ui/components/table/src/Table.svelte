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
  import type { DatasetItem } from "@pixano/core";
  import { icons } from "@pixano/core";

  // Exports
  export let data: any;

  // Calculate row headers
  const featureNames = data[0].map((feature) => {
    return { name: feature.name, type: feature.dtype };
  });

  const dispatch = createEventDispatcher();

  // Select an item
  function handleSelectItem(item: DatasetItem) {
    const itemId = item.find((feature) => {
      return feature.name === "id";
    }).value;
    dispatch("selectItem", itemId);
  }
</script>

<div
  class="h-full w-full overflow-y-auto overflow-x-auto
  rounded-sm bg-white border border-slate-200 shadow-sm shadow-zinc-200"
>
  <table class="table-auto z-0 w-full text-center text-base">
    <!-- Header -->
    <thead>
      <tr class="sticky top-0 bg-white capitalize shadow-sm shadow-slate-200">
        {#each featureNames as { name, type }}
          {#if type != "hidden"}
            <th class="py-4 font-semibold">{name}</th>
          {/if}
        {/each}
        <th />
      </tr>
    </thead>
    <!-- Rows -->
    <tbody>
      {#each data as row}
        <tr
          class="cursor-pointer hover:bg-slate-50"
          on:click={() => {
            handleSelectItem(row);
          }}
        >
          {#each row as cell}
            {#if cell.dtype != "hidden"}
              <td class="py-1 border-b border-slate-200">
                <TableCell itemFeature={cell} />
              </td>
            {/if}
          {/each}
          <td class="py-1 border-b border-slate-200">
            <svg
              xmlns="http://www.w3.org/2000/svg"
              height="48"
              viewBox="0 -960 960 960"
              width="48"
              class="h-8 w-8 mx-auto p-2 border rounded-full border-slate-200 hover:bg-slate-100"
            >
              <title>Open</title>
              <path d={icons.svg_right_arrow} fill="currentcolor" />
            </svg>
          </td>
        </tr>
      {/each}
    </tbody>
  </table>
</div>
