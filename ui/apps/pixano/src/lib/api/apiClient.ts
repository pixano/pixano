/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

export const JSON_HEADERS = {
  Accept: "application/json",
  "Content-Type": "application/json",
} as const;

/**
 * Shared fetch wrapper that handles try/catch, response.ok check, error logging, and fallback.
 *
 * For simple GET-and-return-JSON calls, pass only `url`, `init`, `fallback`, and `label`.
 * For calls needing a transform (e.g. `new DatasetItem(raw)`), pass a `transform` callback.
 */
export async function apiFetch<T>(
  url: string,
  init: RequestInit,
  fallback: T,
  label: string,
  transform?: (json: unknown) => T,
): Promise<T> {
  try {
    const response = await fetch(url, init);
    if (response.ok) {
      const json: unknown = await response.json();
      return transform ? transform(json) : (json as T);
    }
    console.error(`api.${label} -`, response.status, response.statusText, await response.text());
  } catch (e) {
    console.error(`api.${label} -`, e);
  }
  return fallback;
}

/**
 * Like `apiFetch` but for fire-and-forget mutations (POST/PUT/DELETE) with no return value.
 */
export async function apiMutate(
  url: string,
  init: RequestInit,
  label: string,
): Promise<void> {
  try {
    const response = await fetch(url, init);
    if (!response.ok) {
      console.error(`api.${label} -`, response.status, response.statusText, await response.text());
    }
  } catch (e) {
    console.error(`api.${label} -`, e);
  }
}
