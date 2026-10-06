/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { LayoutLoad } from "./$types";
import * as api from "$lib/api";

export const load: LayoutLoad = async () => {
  const [datasets, uiOptions] = await Promise.all([api.listDatasets(), api.getUiOptions()]);
  return { datasets, newUiEnabled: uiOptions.new_ui_enabled };
};
