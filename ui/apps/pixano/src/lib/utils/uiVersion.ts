/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

/** Read by the server (`pixano.api.serve`) to pick which UI the root page serves. */
export const UI_VERSION_COOKIE = "pixano_ui_version";
export const NEW_UI_COOKIE_VALUE = "next";
const ONE_YEAR_IN_SECONDS = 31_536_000;

/**
 * Ask the server for the v1.0 workspace UI and reload the root page. The server honours the
 * request only while the deployment enables that UI (ACTIVATE_UI_V1_0).
 */
export function switchToNewUi(): void {
  document.cookie = `${UI_VERSION_COOKIE}=${NEW_UI_COOKIE_VALUE}; max-age=${ONE_YEAR_IN_SECONDS}; path=/`;
  window.location.href = "/";
}
