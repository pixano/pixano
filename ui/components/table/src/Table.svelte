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
  import { createEventDispatcher } from "svelte";
  import TableCell from "./TableCell.svelte";
  import { icons } from "@pixano/core";

  import type { DatasetItem } from "@pixano/core";

  // Exports
  export let items: Array<DatasetItem>;

  // Calculate row headers
  function getColumnNames(items: Array<DatasetItem>): Array<string> {
    const columnNames = ["id", "split"];
    if (items[0]?.views) {
      columnNames.push.apply(columnNames, Object.keys(items[0].views));
    }
    if (items[0]?.features) {
      columnNames.push.apply(columnNames, Object.keys(items[0].features));
    }
    return columnNames;
  }

  const dispatch = createEventDispatcher();

  // Select an item
  function handleSelectItem(item: DatasetItem) {
    dispatch("selectItem", item.id);
  }
</script>

<div
  class="h-full w-full overflow-y-auto overflow-x-auto
  rounded-sm bg-white border border-slate-300 shadow-sm shadow-slate-300"
>
  <table class="table-auto z-0 w-full text-center text-base text-slate-800">
    <!-- Header -->
    <thead>
      <tr class="sticky top-0 bg-white shadow-sm shadow-slate-300 border-b border-b-slate-400">
        {#each getColumnNames(items) as name}
          <th class="py-4 font-semibold">{name}</th>
        {/each}
        <th />
      </tr>
    </thead>
    <!-- Rows -->
    <tbody>
      {#each items as item}
        <tr
          class="cursor-pointer hover:bg-slate-100"
          on:click={() => {
            handleSelectItem(item);
          }}
        >
          <td class="py-1 border-b border-slate-300">
            <TableCell itemFeature={{ name: "id", dtype: "str", value: item.id }} />
          </td>
          <td class="py-1 border-b border-slate-300">
            <TableCell itemFeature={{ name: "split", dtype: "str", value: item.split }} />
          </td>

          {#if item.views}
            {#each Object.values(item.views) as view}
              <td class="py-1 border-b border-slate-300">
                <TableCell
                  itemFeature={{ name: view.id, dtype: view.type, value: view.thumbnail }}
                />
              </td>
            {/each}
          {/if}
          {#if item.features}
            {#each Object.values(item.features) as feature}
              <td class="py-1 border-b border-slate-300">
                <TableCell itemFeature={feature} />
              </td>
            {/each}
          {/if}

          <td class="py-1 border-b border-slate-300">
            <svg
              xmlns="http://www.w3.org/2000/svg"
              height="48"
              viewBox="0 -960 960 960"
              width="48"
              class="h-8 w-8 mx-auto p-1 border rounded-full border-slate-300 transition-colors hover:bg-slate-200"
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
