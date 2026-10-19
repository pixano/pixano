/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { EMPTY_COLOR_BY_CATALOGUE, type ColorByCatalogue } from "./colorByCatalogue";
import {
  browserStorage,
  DEFAULT_COLOR_BY_SETTINGS,
  readStoredColorBySettings,
  writeStoredColorBySettings,
  type ColorBySettings,
  type KeyValueStorage,
} from "./colorBySettings";

/**
 * The "Color by" settings of the dataset open in the workspace.
 *
 * The workspace is not remounted between the records of a dataset, nor when the URL switches to
 * another dataset, so `configure` runs on every record and reads storage only when the dataset
 * changes. Settings are also kept in memory per dataset, for browsers where storage is missing
 * or fails.
 */
export interface ColorBySession {
  readonly datasetId: string | null;
  readonly settings: ColorBySettings;
  readonly catalogue: ColorByCatalogue;
  /** Bind to a dataset and its attributes; returns true when settings or catalogue changed. */
  configure(datasetId: string, catalogue: ColorByCatalogue): boolean;
  /** Unbind; the in-memory copies are kept. */
  reset(): void;
  /** Apply a change and store it; returns true when the settings changed. */
  apply(update: (settings: ColorBySettings) => ColorBySettings): boolean;
}

export function createColorBySession(
  storage: () => KeyValueStorage | null = browserStorage,
): ColorBySession {
  let datasetId: string | null = null;
  let settings: ColorBySettings = DEFAULT_COLOR_BY_SETTINGS;
  let catalogue: ColorByCatalogue = EMPTY_COLOR_BY_CATALOGUE;
  const inMemory = new Map<string, ColorBySettings>();

  return {
    get datasetId() {
      return datasetId;
    },
    get settings() {
      return settings;
    },
    get catalogue() {
      return catalogue;
    },

    configure(nextDatasetId, nextCatalogue) {
      let changed = false;
      if (nextDatasetId !== datasetId) {
        datasetId = nextDatasetId;
        const loaded =
          readStoredColorBySettings(storage(), nextDatasetId) ??
          inMemory.get(nextDatasetId) ??
          DEFAULT_COLOR_BY_SETTINGS;
        changed = loaded !== settings;
        settings = loaded;
      }
      if (nextCatalogue.signature !== catalogue.signature) {
        catalogue = nextCatalogue;
        changed = true;
      }
      return changed;
    },

    reset() {
      datasetId = null;
      settings = DEFAULT_COLOR_BY_SETTINGS;
      catalogue = EMPTY_COLOR_BY_CATALOGUE;
    },

    apply(update) {
      const next = update(settings);
      if (next === settings) return false;
      settings = next;
      if (datasetId !== null) {
        inMemory.set(datasetId, next);
        writeStoredColorBySettings(storage(), datasetId, next);
      }
      return true;
    },
  };
}
