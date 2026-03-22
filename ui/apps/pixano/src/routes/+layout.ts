/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { LayoutLoad } from "./$types";
import * as api from "$lib/api";

export const load: LayoutLoad = async () => {
  const datasets = await api.listDatasets();
  return { datasets };
};
