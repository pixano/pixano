/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { afterEach, describe, expect, it, vi } from "vitest";

import { DATASET_LAYOUT_VERSION, type DatasetLayout } from "../datasetLayout.js";
import {
  DATASET_LAYOUT_KEY_PREFIX,
  localStorageDatasetLayoutRepository as repository,
} from "../datasetLayoutRepository.js";

const LAYOUT: DatasetLayout = {
  version: DATASET_LAYOUT_VERSION,
  views: { cam: { layout: { x: 1, y: 2, w: 3, h: 4 }, hidden: false } },
};

afterEach(() => {
  localStorage.clear();
  vi.restoreAllMocks();
});

describe("localStorageDatasetLayoutRepository", () => {
  it("round-trips an arrangement", () => {
    repository.save("ds-1", LAYOUT);

    expect(repository.load("ds-1")).toEqual(LAYOUT);
  });

  it("namespaces datasets so one arrangement never shadows another", () => {
    repository.save("ds-1", LAYOUT);

    expect(repository.load("ds-2")).toBeNull();
    expect(localStorage.getItem(`${DATASET_LAYOUT_KEY_PREFIX}ds-1`)).not.toBeNull();
  });

  it("reports no arrangement for a dataset that has none", () => {
    expect(repository.load("unknown")).toBeNull();
  });

  it("treats an unparsable entry as no arrangement rather than throwing", () => {
    localStorage.setItem(`${DATASET_LAYOUT_KEY_PREFIX}ds-1`, "{not json");

    expect(repository.load("ds-1")).toBeNull();
  });

  it("treats a structurally invalid entry as no arrangement", () => {
    localStorage.setItem(`${DATASET_LAYOUT_KEY_PREFIX}ds-1`, JSON.stringify({ views: "nope" }));

    expect(repository.load("ds-1")).toBeNull();
  });

  it("stays silent when storage is blocked, so a workspace never fails over a preference", () => {
    // Spy on the live `localStorage` object rather than `Storage.prototype`:
    // happy-dom exposes these as own properties, so a prototype spy is never
    // consulted and the test would pass without exercising anything.
    const blocked = new Error("storage disabled");
    vi.spyOn(localStorage, "setItem").mockImplementation(() => {
      throw blocked;
    });
    vi.spyOn(localStorage, "getItem").mockImplementation(() => {
      throw blocked;
    });

    expect(() => repository.save("ds-1", LAYOUT)).not.toThrow();
    expect(repository.load("ds-1")).toBeNull();
  });
});
