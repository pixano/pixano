/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import {
  createTable,
  type RowData,
  type Table,
  type TableOptions,
  type TableOptionsResolved,
} from "@tanstack/table-core";

/**
 * Creates a reactive TanStack table for Svelte 5.
 *
 * Uses $state for the table state and $effect.pre to sync option changes.
 * Based on the pattern from svelte5-tanstack-table-examples.
 */
export function createSvelteTable<TData extends RowData>(
  options: TableOptions<TData>,
): Table<TData> {
  const resolvedOptions: TableOptionsResolved<TData> = {
    state: {},
    onStateChange() {},
    renderFallbackValue: null,
    ...options,
  };

  const table = createTable(resolvedOptions);

  let internalState = $state(table.initialState);

  table.setOptions((prev) => ({
    ...prev,
    ...options,
    state: {
      ...internalState,
      ...options.state,
    },
    onStateChange: (updater) => {
      if (typeof updater === "function") {
        internalState = updater(internalState);
      } else {
        internalState = updater;
      }
      options.onStateChange?.(updater);
    },
  }));

  $effect.pre(() => {
    table.setOptions((prev) => ({
      ...prev,
      ...options,
      state: {
        ...internalState,
        ...options.state,
      },
      onStateChange: (updater) => {
        if (typeof updater === "function") {
          internalState = updater(internalState);
        } else {
          internalState = updater;
        }
        options.onStateChange?.(updater);
      },
    }));
  });

  return table;
}
