/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { ReactiveReadonly, ReactiveValue } from "$lib/types/store";

export type { ReactiveReadonly, ReactiveValue };

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

/**
 * Creates a read-only reactive derived value.
 * Replaces the verbose 3-line pattern:
 *   const _foo = $derived.by(() => { ... });
 *   export const foo = { get value() { return _foo; } };
 */
export function reactiveDerived<T>(fn: () => T): ReactiveReadonly<T> {
  const _value = $derived.by(fn);
  return {
    get value() {
      return _value;
    },
  };
}

/**
 * Creates a reactive store using $state.raw — no deep proxy overhead.
 * Use for large immutable objects (tensors, model instances) that are
 * always replaced wholesale, never mutated in place.
 */
export function reactiveRawStore<T>(initial: T): ReactiveValue<T> {
  let _value = $state.raw(initial);
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
