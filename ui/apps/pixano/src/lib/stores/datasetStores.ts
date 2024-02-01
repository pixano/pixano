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
import { writable } from "svelte/store";
import type { DatasetInfo } from "@pixano/core/src";

import {
  DEFAULT_DATASET_TABLE_PAGE,
  DEFAULT_DATASET_TABLE_SIZE,
} from "$lib/constants/pixanoConstants";
import type { DatasetTableStore } from "../types/pixanoTypes";

export const defaultDatasetTableValues: DatasetTableStore = {
  currentPage: DEFAULT_DATASET_TABLE_PAGE,
  pageSize: DEFAULT_DATASET_TABLE_SIZE,
  query: {
    model: "",
    search: "",
  },
};

// Exports
export const datasetsStore = writable<DatasetInfo[]>();
export const modelsStore = writable<string[]>([]);
export const isLoadingNewItemStore = writable<boolean>(false);
export const datasetTableStore = writable<DatasetTableStore>(defaultDatasetTableValues);
export const canSaveCurrentItemStore = writable<boolean>();
export const saveCurrentItemStore = writable<{ shouldSave: boolean; canSave: boolean }>({
  shouldSave: false,
  canSave: false,
});
