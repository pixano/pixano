/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { apiFetch } from "./apiClient";
import type { UiOptionsResponse } from "./restTypes";

/** A server that cannot say the new UI is enabled keeps it hidden. */
const NEW_UI_HIDDEN: UiOptionsResponse = { new_ui_enabled: false };

export async function getUiOptions(): Promise<UiOptionsResponse> {
  return apiFetch<UiOptionsResponse>("/app/ui", {}, NEW_UI_HIDDEN, "getUiOptions");
}
