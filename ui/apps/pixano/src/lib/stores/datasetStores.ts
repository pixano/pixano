/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

// Imports
import { writable } from "svelte/store";

import type { DatasetInfo, DatasetSchema, Source } from "@pixano/core";

import {
  DEFAULT_DATASET_TABLE_PAGE,
  DEFAULT_DATASET_TABLE_SIZE,
} from "../constants/pixanoConstants";
import type { DatasetTableStore } from "../types/pixanoTypes";

export const defaultDatasetTableValues: DatasetTableStore = {
  currentPage: DEFAULT_DATASET_TABLE_PAGE,
  pageSize: DEFAULT_DATASET_TABLE_SIZE,
};

// Exports
export const currentDatasetStore = writable<DatasetInfo>();
export const datasetSchema = writable<DatasetSchema>();
export const datasetsStore = writable<DatasetInfo[]>([]);
export const modelsStore = writable<string[]>([]);
export const isLocalSegmentationModel = writable<boolean>(false);
export const sourcesStore = writable<Source[]>([]);
export const isLoadingNewItemStore = writable<boolean>(true);
export const datasetTableStore = writable<DatasetTableStore>(defaultDatasetTableValues);
export const datasetItemIds = writable<Array<string>>([]);
export const datasetTotalItemsCount = writable<number>(0);
export const canSaveCurrentItemStore = writable<boolean>();
export const saveCurrentItemStore = writable<{ shouldSave: boolean; canSave: boolean }>({
  shouldSave: false,
  canSave: false,
});
