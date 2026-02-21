<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">

  // Svelte Imports
  import { ChevronsDown, ChevronsUp, ChevronsUpDown } from "lucide-svelte";
  import SortableList from "svelte-sortable-list";

  // Pixano Core Imports
  import { Button } from "bits-ui";

  import type { TableData, TableRow } from "$lib/types/dataset";
  import { Checkbox } from "bits-ui";
  import { Check } from "lucide-svelte";

  import { icons } from "$lib/ui";
  import { cn } from "$lib/utils/styleUtils";
  import { buttonVariants } from "$lib/utils/buttonVariants";

  import { createSvelteTable } from "./createSvelteTable.svelte";
  import FlexRender from "./FlexRender.svelte";
  import {
    getCoreRowModel,
    type ColumnDef,
    type SortingState,
    type VisibilityState,
    type ColumnOrderState,
  } from "@tanstack/table-core";
  import { TableCell } from "./TableCell";


  interface Props {
    // Exports
    items: TableData;
    disableSort?: boolean;
    onColsort?: (sortKeys: { id: string; order: string }[]) => void;
    onSelectItem?: (id: string) => void;
  }

  let { items, disableSort = false, onColsort, onSelectItem }: Props = $props();

  // Build column definitions from items.columns
  const buildColumns = (): ColumnDef<TableRow>[] => {
    return items.columns.map((col) => ({
      id: col.name,
      accessorKey: col.name,
      header: col.name.replace("_", " "),
      cell: (info) => {
        const cellRenderer = TableCell[col.type];
        if (cellRenderer) {
          return cellRenderer(info.getValue() as never);
        }
        return String(info.getValue() ?? "");
      },
      enableSorting: col.type !== "image" && col.type !== "video",
    }));
  };

  // Build initial column order (images/videos first)
  const buildInitialColumnOrder = (): string[] => {
    const highPriority: string[] = [];
    const lowPriority: string[] = [];
    for (const col of items.columns) {
      if (col.type === "image" || col.type === "video") {
        highPriority.push(col.name);
      } else {
        lowPriority.push(col.name);
      }
    }
    return [...highPriority, ...lowPriority];
  };

  // Table state
  let sorting = $state<SortingState>([{ id: "created_at", desc: false }]);
  let columnOrder = $state<ColumnOrderState>(buildInitialColumnOrder());
  let columnVisibility = $state<VisibilityState>({});

  const columns = buildColumns();

  const table = createSvelteTable({
    get data() { return items.rows; },
    columns,
    getCoreRowModel: getCoreRowModel(),
    manualSorting: true,
    state: {
      get sorting() { return sorting; },
      get columnOrder() { return columnOrder; },
      get columnVisibility() { return columnVisibility; },
    },
    onSortingChange: (updater) => {
      if (typeof updater === "function") {
        sorting = updater(sorting);
      } else {
        sorting = updater;
      }
    },
    onColumnOrderChange: (updater) => {
      if (typeof updater === "function") {
        columnOrder = updater(columnOrder);
      } else {
        columnOrder = updater;
      }
    },
    onColumnVisibilityChange: (updater) => {
      if (typeof updater === "function") {
        columnVisibility = updater(columnVisibility);
      } else {
        columnVisibility = updater;
      }
    },
  });

  const handleSort = (colId: string) => {
    const colDef = table.getColumn(colId);
    if (!colDef?.getCanSort() || disableSort) return;

    colDef.toggleSorting();

    // If no sorts remain, restore default
    if (sorting.length === 0) {
      sorting = [{ id: "created_at", desc: false }];
    }

    onColsort?.(
      sorting.map((s) => ({ id: s.id, order: s.desc ? "desc" : "asc" })),
    );
  };

  // Column visibility tracking by id
  let shownColumnsById = $state(
    Object.fromEntries(columnOrder.map((id) => [id, true])),
  );
  $effect(() => {
    const hidden: VisibilityState = {};
    for (const [id, shown] of Object.entries(shownColumnsById)) {
      if (!shown) hidden[id] = false;
    }
    columnVisibility = Object.fromEntries(
      columnOrder.map((id) => [id, shownColumnsById[id] !== false]),
    );
  });

  const sortList = (ev: { detail: string[] }) => {
    columnOrder = ev.detail;
  };

  function handleSelectItem(id: string) {
    onSelectItem?.(id);
  }

  // Settings popup status
  let popupOpened = $state(false);
</script>

<!-- Settings popup -->
{#if popupOpened}
  <div
    class="fixed w-full h-full z-20 top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 bg-black/40 backdrop-blur-sm
    flex items-center justify-center font-sans"
  >
    <div
      class="px-8 pt-8 flex flex-col
    bg-card border border-border shadow-xl rounded-xl"
    >
      <span class="text-lg font-medium mb-3">Column settings</span>
      <span class="text-sm text-muted-foreground mb-3">
        Drag and drop to re-order, toggle box for visibility.
      </span>
      <div class="flex flex-col space-y-2">
        <SortableList list={columnOrder} on:sort={sortList} >
          {#snippet children({ item })}
                    <div class="py-1 px-2 flex items-center space-x-2 border border-border rounded-md">
              <Checkbox.Root
                id={item}
                bind:checked={shownColumnsById[item]}
                class="peer h-4 w-4 shrink-0 rounded border border-primary ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 data-[state=checked]:bg-primary data-[state=checked]:text-primary-foreground data-[disabled]:cursor-not-allowed data-[disabled]:opacity-50"
              >
                {#snippet children({ checked })}
                  <span class="flex items-center justify-center text-current h-full w-full">
                    {#if checked}
                      <Check class="h-3.5 w-3.5" strokeWidth={3} />
                    {/if}
                  </span>
                {/snippet}
              </Checkbox.Root>
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
                            {/snippet}
                </SortableList>
      </div>

      <div class="my-6 flex justify-end items-end">
        <Button.Root
          type="button"
          class={buttonVariants()}
          onclick={() => {
            popupOpened = false;
          }}
        >
          Done
        </Button.Root>
      </div>
    </div>
  </div>
{/if}

<div
  class="w-full h-full overflow-auto rounded-xl bg-card border border-border shadow-elevation-1 font-sans"
>
  <table
    class="table-auto z-0 w-full text-center text-sm text-foreground border-separate border-spacing-0"
  >
    <!-- Header -->
    <thead class="sticky top-0 z-10">
      {#each table.getHeaderGroups() as headerGroup (headerGroup.id)}
        <tr>
          {#each headerGroup.headers as header (header.id)}
            <th
              onclick={() => handleSort(header.column.id)}
              class="relative py-3 px-2 text-label bg-surface-2 border-b border-border/60"
            >
              <span class="whitespace-nowrap flex items-center gap-1 justify-center">
                {#if !header.isPlaceholder}
                  <FlexRender content={header.column.columnDef.header} />
                {/if}
                {#if !disableSort && header.column.getCanSort()}
                  {#if header.column.getIsSorted() === "asc"}
                    <ChevronsDown />
                  {:else if header.column.getIsSorted() === "desc"}
                    <ChevronsUp />
                  {:else}
                    <ChevronsUpDown class="opacity-20" />
                  {/if}
                {/if}
              </span>
            </th>
          {/each}
          <th class="w-full bg-surface-2 border-b border-border/60"></th>
          <th class="pr-4 bg-surface-2 border-b border-border/60">
            <!-- Settings button -->
            <Button.Root
              type="button"
              class={buttonVariants({ variant: "ghost" })}
              onclick={() => {
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
                <path d={icons.svg_settings} fill="currentcolor" />
              </svg>
            </Button.Root>
          </th>
        </tr>
      {/each}
    </thead>
    <!-- Rows -->
    <tbody>
      {#each table.getRowModel().rows as row (row.id)}
        <tr
          class="h-20 cursor-pointer hover:bg-accent/60 transition-colors"
          onclick={() => {
            handleSelectItem(items.rows[Number(row.id)].id as string);
          }}
        >
          {#each row.getVisibleCells() as cell (cell.id)}
            <td class="px-3 py-1 border-b border-border">
              <FlexRender content={cell.column.columnDef.cell?.(cell.getContext())} />
            </td>
          {/each}
          <td class="w-full border-b border-border"></td>
          <!-- Go Button -->
          <td class="border-b border-border">
            <svg
              xmlns="http://www.w3.org/2000/svg"
              height="48"
              viewBox="0 -960 960 960"
              width="48"
              class="h-8 w-8 mx-auto p-1 ml-3 border rounded-full border-border text-foreground transition-colors hover:bg-accent"
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
