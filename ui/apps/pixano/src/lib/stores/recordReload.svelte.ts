/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { reactiveStore } from "./reactiveStore.svelte";
import { invalidateAll } from "$app/navigation";

/**
 * How many times the open record was read again on request. The workspace shows a record anew only
 * when another one is opened, so as not to lose what is unsaved; it also does each time this moves.
 */
export const recordReloads = reactiveStore<number>(0);

/**
 * Read the open record again from the server, and show it as it now is: after a job wrote to it in
 * the background. What is unsaved is lost: call it only with nothing unsaved.
 */
export async function reloadOpenRecord(): Promise<void> {
  await invalidateAll();
  recordReloads.value += 1;
}
