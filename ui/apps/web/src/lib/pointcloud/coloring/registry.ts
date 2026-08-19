/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { PointCloudColorMode } from "./colorMode.js";
import { cameraProjectionColorMode } from "./modes/cameraProjectionColorMode.js";
import { elevationColorMode } from "./modes/elevationColorMode.js";
import { intensityColorMode } from "./modes/intensityColorMode.js";
import { neutralColorMode } from "./modes/neutralColorMode.js";
import { rangeColorMode } from "./modes/rangeColorMode.js";

/**
 * Every point-cloud colour mode, in menu order. Adding a mode means a module
 * under `modes/` plus one line here — the widget, the scene, the menu and the
 * other modes stay untouched.
 *
 * Registration is explicit rather than a glob over `modes/`: it keeps the menu
 * order intentional instead of alphabetical, matches every other registry in
 * the app (`TOOLS_2D`, `SEED_LOADERS`, `PAYLOAD_BUILDERS`), and leaves the
 * forgotten-line failure mode to `colorModes.test.ts`, which catches it.
 */
export const COLOR_MODES_3D: readonly PointCloudColorMode[] = [
  neutralColorMode,
  elevationColorMode,
  intensityColorMode,
  rangeColorMode,
  cameraProjectionColorMode,
];

/**
 * Mode a widget opens with. Elevation because it needs nothing beyond the
 * geometry: it renders on every cloud, calibrated or not, with no camera and no
 * intensity column.
 */
export const DEFAULT_COLOR_MODE_ID = elevationColorMode.id;

/**
 * Resolve a stored mode id, falling back to the default. Unknown ids are
 * expected rather than exceptional — a widget's persisted choice outlives the
 * mode that produced it if one is ever renamed or removed — so this returns the
 * default instead of throwing, and the user simply sees the cloud's usual
 * colours.
 */
export function colorModeFor(id: string | undefined): PointCloudColorMode {
  const found = COLOR_MODES_3D.find((mode) => mode.id === id);
  if (found) return found;
  // The default is in the list by construction (it is one of its members'
  // ids), so this is a lookup, not a risk of undefined.
  return COLOR_MODES_3D.find((mode) => mode.id === DEFAULT_COLOR_MODE_ID) ?? COLOR_MODES_3D[0];
}
