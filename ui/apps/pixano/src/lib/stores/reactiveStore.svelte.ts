/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { ReactiveValue } from "$lib/types/store";

export type { ReactiveValue };

/**
 * Creates a reactive store wrapping a single value with $state.
 * Replaces the repetitive 5-line pattern:
 *   let _x = $state<T>(initial);
 *   export const x = { get value() { return _x; }, set value(v) { _x = v; }, update(fn) { _x = fn(_x); } };
 */
export function reactiveStore<T>(initial: T): ReactiveValue<T> {
  let _value = $state(initial);
  return {
    get value() {
      return _value;
    },
    set value(v: T) {
      _value = v;
    },
    update(fn: (prev: T) => T) {
      _value = fn(_value);
    },
  };
}
