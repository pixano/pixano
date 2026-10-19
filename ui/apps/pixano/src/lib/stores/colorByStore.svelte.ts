/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { reactiveRawStore, reactiveStore, type ReactiveReadonly } from "./reactiveStore.svelte";
import {
  buildColorByCatalogue,
  EMPTY_COLOR_BY_CATALOGUE,
  type ColorByCatalogue,
} from "$lib/coloring/colorByCatalogue";
import { createColorBySession } from "$lib/coloring/colorBySession";
import {
  DEFAULT_COLOR_BY_SETTINGS,
  withLearned,
  withoutCustomColors,
  withoutSeenRange,
  withRampColor,
  withSelected,
  withValueColor,
  type ColorBySettings,
} from "$lib/coloring/colorBySettings";
import type { PendingLearned } from "$lib/coloring/colorResolver";
import type { WorkspaceManifest } from "$lib/workspace/manifest";

// "Color by" state of the open dataset; the logic lives in $lib/coloring.

const session = createColorBySession();
const catalogue = reactiveRawStore<ColorByCatalogue>(EMPTY_COLOR_BY_CATALOGUE);
const settings = reactiveRawStore<ColorBySettings>(DEFAULT_COLOR_BY_SETTINGS);

/** The attributes the open dataset can be colored by. */
export const colorByCatalogue: ReactiveReadonly<ColorByCatalogue> = {
  get value() {
    return catalogue.value;
  },
};

export const colorBySettings: ReactiveReadonly<ColorBySettings> = {
  get value() {
    return settings.value;
  },
};

/** Whether the legend is shown; kept while the app is open, across records and datasets. */
export const colorByLegendOpen = reactiveStore(true);

function mirrorSession(): void {
  catalogue.value = session.catalogue;
  settings.value = session.settings;
}

function update(change: (current: ColorBySettings) => ColorBySettings): void {
  if (session.apply(change)) settings.value = session.settings;
}

/** Bind to the dataset of the record being opened; storage is read when the dataset changes. */
export function configureColorBy(
  datasetId: string,
  manifest: WorkspaceManifest | null | undefined,
): void {
  if (session.configure(datasetId, buildColorByCatalogue(manifest))) mirrorSession();
}

export function resetColorBy(): void {
  session.reset();
  mirrorSession();
}

export function selectColorBy(optionId: string): void {
  update((current) => withSelected(current, optionId));
}

export function setColorByValueColor(attributeId: string, key: string, color: string): void {
  update((current) => withValueColor(current, attributeId, key, color));
}

export function setColorByRampColor(attributeId: string, end: "low" | "high", color: string): void {
  update((current) => withRampColor(current, attributeId, end, color));
}

export function resetColorByColors(attributeId: string): void {
  update((current) => withoutCustomColors(current, attributeId));
}

export function resetColorByRange(attributeId: string): void {
  update((current) => withoutSeenRange(current, attributeId));
}

export function rememberColorByLearned(pending: PendingLearned): void {
  update((current) => withLearned(current, pending.attributeId, pending));
}
