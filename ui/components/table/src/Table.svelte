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

  // Local Imports
  import { DefaultCell, FeatureCell, ImgCell } from "./cells";

  // Pixano Core Imports
  import { icons } from "@pixano/core";
  import type { DatasetItem } from "@pixano/core";
  import Button from "@pixano/core/src/components/ui/button/button.svelte";
  import Checkbox from "@pixano/core/src/components/ui/checkbox/checkbox.svelte";

  // Svelte Imports
  import { createEventDispatcher } from "svelte";
  import { readable } from "svelte/store";
  import SortableList from "svelte-sortable-list";
  import { createTable, Subscribe, Render } from "svelte-headless-table";
  import { addColumnOrder, addHiddenColumns } from "svelte-headless-table/plugins";

  // Exports
  export let items: Array<DatasetItem>;

  // Handler to select an item
  const dispatch = createEventDispatcher();
  function handleSelectItem(id: number) {
    dispatch("selectItem", id);
  }

  // Add data into a readable store
  const data = readable(items);

  // Create table object
  const table = createTable(data, {
    colOrder: addColumnOrder(),
    hideCols: addHiddenColumns(),
  });

  // Initialise columns
  let itemColumns = [
    table.column({
      header: "ID",
      cell: DefaultCell,
      accessor: "id",
    }),
    table.column({
      header: "Split",
      cell: DefaultCell,
      accessor: "split",
    }),
  ];
  let colOrder: string[] = [];

  // Parse views and add them to the columns
  if (items[0]?.views) {
    Object.values(items[0].views).forEach(({ id }) => {
      itemColumns.push(
        table.column({
          header: id,
          cell: ImgCell,
          accessor: (item) => JSON.stringify(item.views[id]),
        }),
      );
      colOrder.push(id);
    });
  }

  // Add id and split to column order
  colOrder.push("id");
  colOrder.push("split");

  // Parse features and add them to the columns
  if (items[0]?.features) {
    Object.values(items[0].features).forEach(({ name }) => {
      itemColumns.push(
        table.column({
          header: name,
          cell: FeatureCell,
          accessor: (item) => JSON.stringify(item.features[name]),
        }),
      );
      colOrder.push(name);
    });
  }

  // Create columns
  const columns = table.createColumns(itemColumns);

  // Create view model
  const { headerRows, rows, tableAttrs, tableBodyAttrs, pluginStates } =
    table.createViewModel(columns);

  // Order columns
  const { columnIdOrder } = pluginStates.colOrder;
  $columnIdOrder = [...colOrder];

  // Handle column re-order
  const sortList = (ev: { detail: string[] }) => {
    $columnIdOrder = ev.detail;
  };

  // Column visibility
  const { hiddenColumnIds } = pluginStates.hideCols;
  let shownColumnsById = Object.fromEntries($columnIdOrder.map((id) => [id, true]));
  $: $hiddenColumnIds = Object.entries(shownColumnsById)
    .filter(([, hide]) => !hide)
    .map(([id]) => id);

  // Settings popup status
  let popupOpened = false;
</script>

<!-- Settings popup -->
<div
  class="fixed w-full h-full z-20 top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 bg-gray-500/30 backdrop:blur-lg
    flex items-center justify-center font-Montserrat
    {popupOpened ? 'block' : 'hidden'}"
>
  <div
    class="px-12 pt-10 flex flex-col
    bg-white border border-slate-300 shadow-sm shadow-slate-300 rounded-lg"
  >
    <span class="text-3xl font-bold mb-4"> Column settings </span>
    <span class="text-sm italic text-gray-500 font-medium mb-3">
      Drag and drop to re-order, toggle box for visibility.
    </span>
    <div class="flex flex-col space-y-2">
      <SortableList list={$columnIdOrder} on:sort={sortList} let:item>
        <div class="py-1 px-2 flex items-center space-x-2 border rounded-sm">
          <Checkbox id={item} bind:checked={shownColumnsById[item]}></Checkbox>
          <label for={item} class="text-sm select-none grow cursor-pointer">
            {item}
          </label>
          <svg
            xmlns="http://www.w3.org/2000/svg"
            height="48"
            viewBox="0 -960 960 960"
            width="48"
            class="h-6 w-6 cursor-move"
          >
            <path d={icons.svg_drag_handle} fill="grey" />
          </svg>
        </div>
      </SortableList>
    </div>

    <div class="my-6 flex justify-end items-end">
      <Button
        class="text-white"
        on:click={() => {
          popupOpened = false;
        }}
      >
        Done
      </Button>
    </div>
  </div>
</div>
<div
  class="h-full w-full overflow-y-auto overflow-x-auto
    rounded-sm bg-white border border-slate-300 shadow-sm shadow-slate-300 font-Montserrat"
>
  <table {...$tableAttrs} class="table-auto z-0 w-full text-center text-base text-slate-800">
    <!-- Header -->
    <thead>
      {#each $headerRows as headerRow (headerRow.id)}
        <Subscribe rowAttrs={headerRow.attrs()} let:rowAttrs>
          <tr
            {...rowAttrs}
            class="sticky top-0 z-10 bg-white shadow-sm shadow-slate-300 border-b border-b-slate-400"
          >
            {#each headerRow.cells as cell (cell.id)}
              <Subscribe attrs={cell.attrs()} let:attrs>
                <th {...attrs} class="relative py-4 font-semibold">
                  <Render of={cell.render()} />
                </th>
              </Subscribe>
            {/each}
            <th class="w-full"></th>
            <th class="pr-4">
              <!-- Settings button -->
              <Button
                variant="ghost"
                on:click={() => {
                  popupOpened = true;
                }}
              >
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  height="48"
                  viewBox="0 -960 960 960"
                  width="48"
                  class="h-6 w-6"
                >
                  <title></title>
                  <path d={icons.svg_settings} fill="#111" />
                </svg>
              </Button>
            </th>
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
            class="h-24 cursor-pointer hover:bg-slate-100"
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
            <td class="w-full border-b border-slate-300"></td>
            <!-- Go Button -->
            <td class="border-b border-slate-300">
              <svg
                xmlns="http://www.w3.org/2000/svg"
                height="48"
                viewBox="0 -960 960 960"
                width="48"
                class="h-8 w-8 mx-auto p-1 ml-3 border rounded-full border-slate-300 transition-colors hover:bg-slate-200"
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
