/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

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
};

// Exports
export const currentDatasetStore = writable<DatasetInfo>();
export const datasetsStore = writable<DatasetInfo[]>();
export const modelsStore = writable<string[]>([]);
export const isLoadingNewItemStore = writable<boolean>(false);
export const datasetTableStore = writable<DatasetTableStore>(defaultDatasetTableValues);
export const canSaveCurrentItemStore = writable<boolean>();
export const saveCurrentItemStore = writable<{ shouldSave: boolean; canSave: boolean }>({
  shouldSave: false,
  canSave: false,
});
