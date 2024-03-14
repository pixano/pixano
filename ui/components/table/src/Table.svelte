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
  import TableCell from "./TableCell.svelte";
  import { icons } from "@pixano/core";
  import { createEventDispatcher } from "svelte";
  import { readable } from "svelte/store";
  import { createTable, Subscribe, Render, createRender } from "svelte-headless-table";
  import { addSortBy, addColumnOrder } from "svelte-headless-table/plugins";

  import type { DatasetItem, ItemFeature, ItemView } from "@pixano/core";

  // Exports
  export let items: Array<DatasetItem>;

  // Add data into a readable store
  const data = readable(items);

  // Create table object
  const table = createTable(data, {
    sort: addSortBy({ disableMultiSort: true }),
    colOrder: addColumnOrder(),
  });

  // Initialise columns
  let itemColumns = [
    table.column({
      header: "ID",
      accessor: "id",
      plugins: {
        sort: { invert: true },
      },
    }),
    table.column({
      header: "Split",
      accessor: "split",
    }),
  ];
  let colOrder = [];

  // Parse views and add them to the columns
  const ImgCell = (feature) => {
    let img: ItemView = JSON.parse(feature.value) as ItemView; // 'as ItemView' will provoc a linting error if removed
    //console.log({ name: img.id, dtype: img.type, value: img.thumbnail })
    return createRender(TableCell, {
      itemFeature: { name: img.id, dtype: img.type, value: img.thumbnail },
    });
  };
  if (items[0]?.views) {
    Object.values(items[0].views).forEach(({ id }) => {
      itemColumns.push(
        table.column({
          header: id,
          cell: ImgCell,
          accessor: (item) => JSON.stringify(item.views[id]),
          plugins: {
            sort: { disable: true },
          },
        }),
      );
      colOrder.push(id);
    });
  }

  // Parse features and add them to the columns
  const FeatureCell = (feature) =>
    createRender(TableCell, {
      itemFeature: JSON.parse(feature.value) as ItemFeature, // 'as ItemFeature' will provoc a linting error if removed,
    });
  if (items[0]?.features) {
    Object.values(items[0].features).forEach(({ name }) => {
      itemColumns.push(
        table.column({
          header: name,
          cell: FeatureCell,
          accessor: (item) => JSON.stringify(item.features[name]),
          plugins: {
            sort: { disable: true },
          },
        }),
      );
    });
  }

  // Create columns
  const columns = table.createColumns(itemColumns);

  // Create view model
  const { headerRows, rows, tableAttrs, tableBodyAttrs, pluginStates } =
    table.createViewModel(columns);

  // Order columns
  const { columnIdOrder } = pluginStates.colOrder;
  $columnIdOrder = [...colOrder, "id", "split"];

  const dispatch = createEventDispatcher();

  // Select an item
  function handleSelectItem(id: number) {
    dispatch("selectItem", id);
  }
</script>

<div
  class="h-full w-full overflow-y-auto overflow-x-auto
  rounded-sm bg-white border border-slate-300 shadow-sm shadow-slate-300"
>
  <table {...$tableAttrs} class="table-fixed z-0 w-full text-center text-base text-slate-800">
    <!-- Header -->
    <thead>
      {#each $headerRows as headerRow (headerRow.id)}
        <Subscribe rowAttrs={headerRow.attrs()} let:rowAttrs>
          <tr
            {...rowAttrs}
            class="sticky top-0 z-10 bg-white shadow-sm shadow-slate-300 border-b border-b-slate-400"
          >
            {#each headerRow.cells as cell (cell.id)}
              <Subscribe attrs={cell.attrs()} let:attrs props={cell.props()} let:props>
                <th {...attrs} on:click={props.sort.toggle} class="py-4 font-semibold">
                  <Render of={cell.render()} />
                  {#if props.sort.order === "asc"}
                    ⬇️
                  {:else if props.sort.order === "desc"}
                    ⬆️
                  {/if}
                </th>
              </Subscribe>
            {/each}
            <th class="w-24" />
          </tr>
        </Subscribe>
      {/each}
    </thead>
    <!-- Rows -->
    <tbody {...$tableBodyAttrs}>
      {#each $rows as row (row.id)}
        <Subscribe rowAttrs={row.attrs()} let:rowAttrs>
          <tr
            {...rowAttrs}
            class="cursor-pointer hover:bg-slate-100"
            on:click={() => {
              handleSelectItem(row.original.id); // or row.cellForId.id.value
            }}
          >
            {#each row.cells as cell (cell.id)}
              <Subscribe attrs={cell.attrs()} let:attrs>
                <td {...attrs} class="border-b border-slate-300">
                  <Render of={cell.render()} />
                </td>
              </Subscribe>
            {/each}
            <!-- Go Button -->
            <td class="border-b border-slate-300">
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
        </Subscribe>
      {/each}
    </tbody>
  </table>
</div>
