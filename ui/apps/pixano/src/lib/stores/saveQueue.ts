/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { ResourceMutation } from "$lib/api/resourcePayloads";

export interface SaveAttempt {
  readonly id: number;
  readonly generation: number;
  readonly mutation: ResourceMutation;
}

function sameTarget(left: ResourceMutation, right: ResourceMutation): boolean {
  return left.target.resource === right.target.resource && left.target.id === right.target.id;
}

function mergeMutation(
  existing: ResourceMutation | undefined,
  incoming: ResourceMutation,
): ResourceMutation | undefined {
  if (!existing) return incoming;
  if (existing.op === "create") {
    return incoming.op === "delete" ? undefined : { ...incoming, op: "create" };
  }
  if (existing.op === "delete") {
    return incoming.op === "delete" ? existing : { ...incoming, op: "update" };
  }
  return incoming.op === "create" ? { ...incoming, op: "update" } : incoming;
}

function priority(mutation: ResourceMutation): number {
  if (mutation.op === "delete") {
    if (mutation.target.resource === "entities") return 4;
    if (mutation.target.resource === "tracklets") return 3;
    return 2;
  }
  if (mutation.target.resource === "entities") return 0;
  if (mutation.target.resource === "tracklets") return 1;
  return 2;
}

/** Pending intent is separate from an immutable, possibly committed request. */
export function createSaveQueue(onChange?: (mutations: ResourceMutation[]) => void) {
  let pending: ResourceMutation[] = [];
  let active: SaveAttempt | null = null;
  let generation = 0;
  let nextId = 1;

  const snapshot = () => [...(active ? [active.mutation] : []), ...pending];
  const publish = () => onChange?.(snapshot());

  function stage(mutation: ResourceMutation) {
    // Payloads may contain arrays shared with mutable Svelte annotation objects.
    const incoming = JSON.parse(JSON.stringify(mutation)) as ResourceMutation;
    if (
      active?.mutation.op === "create" &&
      incoming.op === "create" &&
      sameTarget(active.mutation, incoming)
    ) {
      incoming.op = "update";
    }
    const existing = pending.find((entry) => sameTarget(entry, incoming));
    pending = pending.filter((entry) => !sameTarget(entry, incoming));
    const merged = mergeMutation(existing, incoming);
    if (merged) pending.push(merged);
    publish();
  }

  function next(): SaveAttempt | null {
    if (active) return active;
    const ordered = [...pending].sort((left, right) => priority(left) - priority(right));
    const mutation = ordered[0];
    if (!mutation) return null;
    pending = pending.filter((entry) => entry !== mutation);
    active = { id: nextId++, generation, mutation };
    publish();
    return active;
  }

  function matches(attempt: SaveAttempt): boolean {
    return generation === attempt.generation && active?.id === attempt.id;
  }

  function acknowledge(attempt: SaveAttempt): boolean {
    if (!matches(attempt)) return false;
    active = null;
    publish();
    return true;
  }

  function fail(attempt: SaveAttempt, outcome: "unchanged" | "unknown") {
    if (!matches(attempt) || outcome === "unknown") return;
    // A definite rejection did not write: newer intent can safely supersede it.
    const newer = pending.find((entry) => sameTarget(entry, attempt.mutation));
    pending = pending.filter((entry) => !sameTarget(entry, attempt.mutation));
    const merged = newer ? mergeMutation(attempt.mutation, newer) : attempt.mutation;
    if (merged) pending.unshift(merged);
    active = null;
    publish();
  }

  return {
    get generation() {
      return generation;
    },
    get mutations() {
      return snapshot();
    },
    stage,
    next,
    acknowledge,
    fail,
    reset() {
      generation++;
      pending = [];
      active = null;
      publish();
    },
  };
}

export type SaveQueue = ReturnType<typeof createSaveQueue>;
