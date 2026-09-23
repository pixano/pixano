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
  type TableState,
} from "@tanstack/table-core";

type StateSource = () => Record<string | symbol, unknown>;

/**
 * Lazy getter-forwarding merge of table-state sources (later sources win).
 *
 * TanStack reads `table.getState().x` at RENDER time; forwarding each property
 * access to the live sources means reads of `$state`-backed getters happen
 * inside the template's reactive context and register as Svelte dependencies.
 * An eager object spread would snapshot the getters once and freeze the state —
 * the template would then never re-render on column order/visibility changes.
 */
function lazyMergeState(...sources: StateSource[]): TableState {
  return new Proxy({} as TableState, {
    get(_, key) {
      for (let i = sources.length - 1; i >= 0; i--) {
        const src = sources[i]();
        if (src && key in src) return src[key];
      }
      return undefined;
    },
    has(_, key) {
      return sources.some((source) => {
        const src = source();
        return Boolean(src) && key in src;
      });
    },
    ownKeys() {
      const keys = new Set<string | symbol>();
      for (const source of sources) {
        const src = source();
        if (src) for (const key of Reflect.ownKeys(src)) keys.add(key);
      }
      return [...keys];
    },
    getOwnPropertyDescriptor(_, key) {
      for (let i = sources.length - 1; i >= 0; i--) {
        const src = sources[i]();
        if (src && key in src) {
          return { enumerable: true, configurable: true, value: src[key] };
        }
      }
      return undefined;
    },
  });
}

/**
 * Creates a reactive TanStack table for Svelte 5.
 *
 * Uses $state for the table state and $effect.pre to sync option changes.
 * State is merged LAZILY (see `lazyMergeState`) so render-time `getState()`
 * reads forward to the caller's `$state` getters and track as dependencies.
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

  const mergedState = lazyMergeState(
    () => internalState as unknown as Record<string | symbol, unknown>,
    () => (options.state ?? {}) as Record<string | symbol, unknown>,
  );

  const applyOptions = () => {
    table.setOptions((prev) => ({
      ...prev,
      ...options,
      state: mergedState,
      onStateChange: (updater) => {
        if (typeof updater === "function") {
          internalState = updater(internalState);
        } else {
          internalState = updater;
        }
        options.onStateChange?.(updater);
      },
    }));
  };

  applyOptions();

  $effect.pre(() => {
    applyOptions();
  });

  return table;
}
