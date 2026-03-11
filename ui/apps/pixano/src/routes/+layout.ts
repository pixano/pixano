/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { LayoutLoad } from "./$types";
import * as api from "$lib/api";
import { checkInferenceStatus } from "$lib/services/inferenceService";

export const load: LayoutLoad = async () => {
  const [datasets] = await Promise.all([api.listDatasets(), checkInferenceStatus()]);
  return { datasets };
};
