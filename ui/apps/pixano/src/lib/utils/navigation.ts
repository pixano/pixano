/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { goto } from "$app/navigation";
import { isNavigationCancellation } from "$lib/stores/navigationGuard";

/** A route guard canceling a requested navigation is an expected user interaction. */
export async function navigateToRoute(route: string): Promise<void> {
  try {
    await goto(route);
  } catch (error) {
    if (!isNavigationCancellation(error)) throw error;
  }
}
