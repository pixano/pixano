<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Svelte Imports
  import {
    getCoreRowModel,
    type ColumnDef,
    type ColumnOrderState,
    type VisibilityState,
  } from "@tanstack/table-core";
  // Pixano Core Imports
  import { Checkbox, Popover } from "bits-ui";
  import {
    ArrowRight,
    CaretDown,
    CaretUp,
    CaretUpDown,
    Check,
    GearSix,
    Images,
  } from "phosphor-svelte";

  import { createSvelteTable } from "./createSvelteTable.svelte";
  import FlexRender from "./FlexRender.svelte";
  import { TableCell } from "./TableCell";
  import type { TableData, TableRow } from "$lib/types/dataset";
  import { formatColumnLabel } from "$lib/utils/columns";

  interface Props {
    // Exports
    items: TableData;
    activeSort?: { col: string; order: string };
    onColsort?: (sortKeys: { id: string; order: string }[]) => void;
    onSelectItem?: (id: string) => void;
    /** When set, each row shows a "Find similar" action emitting the record id. */
    onFindSimilar?: (id: string) => void;
  }

  let { items, activeSort, onColsort, onSelectItem, onFindSimilar }: Props = $props();

  // Build column definitions from items.columns
  const buildColumns = (): ColumnDef<TableRow>[] => {
    return items.columns.map((col) => ({
      id: col.name,
      accessorKey: col.name,
      header: formatColumnLabel(col.name),
      cell: (info) => {
        const cellRenderer = TableCell[col.type];
        if (cellRenderer) {
          return cellRenderer(info.getValue() as never);
        }
        const val = info.getValue();
        return val == null ? "" : String(val as string | number | boolean);
      },
      enableSorting: col.type !== "image" && col.type !== "video" && col.type !== "list",
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

  const initialColumnOrder = buildInitialColumnOrder();
  let columnOrder = $state<ColumnOrderState>(initialColumnOrder);
  let columnVisibility = $state<VisibilityState>({});

  const columns = buildColumns();

  const table = createSvelteTable({
    get data() {
      return items.rows;
    },
    columns,
    getCoreRowModel: getCoreRowModel(),
    manualSorting: true,
    state: {
      get columnOrder() {
        return columnOrder;
      },
      get columnVisibility() {
        return columnVisibility;
      },
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

  // Sorting is fully server-driven: carets reflect the activeSort prop, and a header
  // click cycles asc → desc → clear via onColsort. No table remount, no local state.
  function sortStateOf(colId: string): "asc" | "desc" | null {
    if (activeSort?.col !== colId) return null;
    return activeSort.order === "desc" ? "desc" : "asc";
  }

  const handleSort = (colId: string) => {
    if (!table.getColumn(colId)?.getCanSort()) return;
    const current = sortStateOf(colId);
    if (current === null) onColsort?.([{ id: colId, order: "asc" }]);
    else if (current === "asc") onColsort?.([{ id: colId, order: "desc" }]);
    else onColsort?.([]);
  };

  // Column visibility tracking by id
  let shownColumnsById = $state(Object.fromEntries(initialColumnOrder.map((id) => [id, true])));
  $effect(() => {
    columnVisibility = Object.fromEntries(
      columnOrder.map((id) => [id, shownColumnsById[id] !== false]),
    );
  });

  const moveColumn = (index: number, delta: number) => {
    const target = index + delta;
    if (target < 0 || target >= columnOrder.length) return;
    const next = [...columnOrder];
    [next[index], next[target]] = [next[target], next[index]];
    columnOrder = next;
  };

  function handleSelectItem(id: string) {
    onSelectItem?.(id);
  }

  function recordIdOf(rowId: string): string {
    return items.rows[Number(rowId)].id as string;
  }

  let settingsOpen = $state(false);

  const rowActionClass =
    "flex h-8 w-8 items-center justify-center border rounded-full border-border text-foreground transition-colors hover:bg-accent hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring";
</script>

<div class="w-full h-full overflow-auto font-sans">
  <table
    class="table-auto z-0 w-full text-center text-sm text-foreground border-separate border-spacing-0"
  >
    <!-- Header -->
    <thead class="sticky top-0 z-10">
      {#each table.getHeaderGroups() as headerGroup (headerGroup.id)}
        <tr>
          {#each headerGroup.headers as header (header.id)}
            {@const sorted = sortStateOf(header.column.id)}
            <th class="bg-surface-2 border-b border-border/60 px-2">
              {#if header.column.getCanSort()}
                <button
                  type="button"
                  onclick={() => handleSort(header.column.id)}
                  aria-label="Sort by {formatColumnLabel(header.column.id)}"
                  class="group w-full py-3 px-1 text-label whitespace-nowrap flex items-center gap-1 justify-center rounded-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  {#if !header.isPlaceholder}
                    <FlexRender content={header.column.columnDef.header} />
                  {/if}
                  {#if sorted === "asc"}
                    <CaretUp size={14} weight="bold" class="text-primary" />
                  {:else if sorted === "desc"}
                    <CaretDown size={14} weight="bold" class="text-primary" />
                  {:else}
                    <CaretUpDown
                      size={14}
                      class="opacity-40 group-hover:opacity-100 transition-opacity"
                    />
                  {/if}
                </button>
              {:else}
                <span
                  class="py-3 px-1 text-label whitespace-nowrap flex items-center justify-center"
                >
                  {#if !header.isPlaceholder}
                    <FlexRender content={header.column.columnDef.header} />
                  {/if}
                </span>
              {/if}
            </th>
          {/each}
          <th class="w-full bg-surface-2 border-b border-border/60"></th>
          <th class="pr-4 bg-surface-2 border-b border-border/60">
            <!-- Column settings -->
            <Popover.Root bind:open={settingsOpen}>
              <Popover.Trigger
                aria-label="Column settings"
                class="inline-flex h-8 w-8 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-accent hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                <GearSix size={16} />
              </Popover.Trigger>
              <Popover.Portal>
                <Popover.Content
                  align="end"
                  sideOffset={8}
                  class="z-50 w-72 rounded-2xl border border-border/50 bg-popover/95 p-3 text-popover-foreground shadow-elevation-2 backdrop-blur-md"
                >
                  <p class="text-label mb-1 text-left">Columns</p>
                  <p
                    class="text-xs text-muted-foreground mb-3 text-left font-normal normal-case tracking-normal"
                  >
                    Toggle to show or hide, arrows to reorder.
                  </p>
                  <div class="flex flex-col space-y-1.5">
                    {#each columnOrder as item, index (item)}
                      <div
                        class="py-1.5 px-2 flex items-center gap-2 border border-border/60 rounded-lg bg-background"
                      >
                        <Checkbox.Root
                          id={item}
                          checked={shownColumnsById[item] !== false}
                          onCheckedChange={(checked) => {
                            shownColumnsById[item] = checked === true;
                          }}
                          class="peer h-4 w-4 shrink-0 rounded border border-primary transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring data-[state=checked]:bg-primary data-[state=checked]:text-primary-foreground"
                        >
                          {#snippet children({ checked })}
                            <span
                              class="flex items-center justify-center text-current h-full w-full"
                            >
                              {#if checked}
                                <Check class="h-3 w-3" />
                              {/if}
                            </span>
                          {/snippet}
                        </Checkbox.Root>
                        <label
                          for={item}
                          class="text-sm font-normal normal-case tracking-normal select-none grow cursor-pointer text-left truncate"
                        >
                          {formatColumnLabel(item)}
                        </label>
                        <button
                          type="button"
                          aria-label="Move {formatColumnLabel(item)} up"
                          disabled={index === 0}
                          onclick={() => moveColumn(index, -1)}
                          class="p-1 rounded-md text-muted-foreground hover:bg-accent hover:text-foreground disabled:opacity-25 disabled:pointer-events-none focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                        >
                          <CaretUp size={13} weight="bold" />
                        </button>
                        <button
                          type="button"
                          aria-label="Move {formatColumnLabel(item)} down"
                          disabled={index === columnOrder.length - 1}
                          onclick={() => moveColumn(index, 1)}
                          class="p-1 rounded-md text-muted-foreground hover:bg-accent hover:text-foreground disabled:opacity-25 disabled:pointer-events-none focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                        >
                          <CaretDown size={13} weight="bold" />
                        </button>
                      </div>
                    {/each}
                  </div>
                </Popover.Content>
              </Popover.Portal>
            </Popover.Root>
          </th>
        </tr>
      {/each}
    </thead>
    <!-- Rows -->
    <tbody>
      {#each table.getRowModel().rows as row (row.id)}
        <tr
          class="h-14 cursor-pointer hover:bg-accent/60 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring"
          tabindex="0"
          onclick={() => {
            handleSelectItem(recordIdOf(row.id));
          }}
          onkeydown={(event: KeyboardEvent) => {
            if (event.key === "Enter" || event.key === " ") {
              event.preventDefault();
              handleSelectItem(recordIdOf(row.id));
            }
          }}
        >
          {#each row.getVisibleCells() as cell (cell.id)}
            <td
              class="px-3 py-1 border-b border-border/60 {cell.column.id === 'id'
                ? 'font-mono text-xs text-muted-foreground'
                : ''}"
            >
              <!-- eslint-disable-next-line @typescript-eslint/no-unsafe-call, @typescript-eslint/no-explicit-any -->
              <FlexRender content={(cell.column.columnDef.cell as any)?.(cell.getContext())} />
            </td>
          {/each}
          <td class="w-full border-b border-border/60"></td>
          <!-- Row actions -->
          <td class="border-b border-border/60 pr-4">
            <div class="flex items-center justify-end gap-1.5">
              {#if onFindSimilar}
                <button
                  type="button"
                  title="More like this"
                  aria-label="More like this"
                  class={rowActionClass}
                  onclick={(event: MouseEvent) => {
                    event.stopPropagation();
                    onFindSimilar(recordIdOf(row.id));
                  }}
                >
                  <Images size={15} />
                </button>
              {/if}
              <button
                type="button"
                title="Open record"
                aria-label="Open record"
                class={rowActionClass}
                onclick={(event: MouseEvent) => {
                  event.stopPropagation();
                  handleSelectItem(recordIdOf(row.id));
                }}
              >
                <ArrowRight size={15} />
              </button>
            </div>
          </td>
        </tr>
      {/each}
    </tbody>
  </table>
</div>
