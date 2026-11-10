/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

export const JSON_HEADERS = {
  Accept: "application/json",
  "Content-Type": "application/json",
} as const;

export class ApiError extends Error {
  status: number;
  body: string;

  constructor(message: string, status: number, body: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }
}

function logApiError(label: string, error: unknown): void {
  console.error(`api.${label} -`, error);
}

export function buildQueryString(
  params: Record<string, string | number | boolean | string[] | null | undefined>,
): string {
  const searchParams = new URLSearchParams();

  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") {
      continue;
    }
    // Arrays become repeated params (e.g. filter=a&filter=b) — the shape the
    // records endpoint's `filter` query param expects.
    if (Array.isArray(value)) {
      for (const item of value) {
        if (item !== undefined && item !== null && item !== "") {
          searchParams.append(key, String(item));
        }
      }
      continue;
    }
    searchParams.set(key, String(value));
  }

  const query = searchParams.toString();
  return query ? `?${query}` : "";
}

/**
 * The server's own words for a request it failed, from the `detail` of a FastAPI error body: a
 * sentence, the first of a list of refusals, or the message of a coded error — a dataset busy
 * being written. Null when the error carries none.
 */
export function serverDetail(error: unknown): string | null {
  if (!(error instanceof ApiError)) return null;
  let parsed: unknown;
  try {
    parsed = JSON.parse(error.body);
  } catch {
    return null;
  }
  const detail = (parsed as { detail?: unknown } | null)?.detail;
  if (typeof detail === "string" && detail) return detail;
  if (Array.isArray(detail) && detail.length > 0) {
    const first = detail[0] as { msg?: unknown } | null;
    if (typeof first?.msg === "string") return first.msg;
  }
  const message = (detail as { message?: unknown } | null)?.message;
  return typeof message === "string" && message ? message : null;
}

export async function requestJson<T>(
  url: string,
  init: RequestInit = {},
  label: string,
): Promise<T> {
  const response = await fetch(url, init);
  if (!response.ok) {
    const body = await response.text();
    const error = new ApiError(
      `${label} failed with ${response.status} ${response.statusText}`,
      response.status,
      body,
    );
    logApiError(label, error);
    throw error;
  }
  return (await response.json()) as T;
}

export async function requestBlob(
  url: string,
  init: RequestInit = {},
  label: string,
): Promise<Blob> {
  const response = await fetch(url, init);
  if (!response.ok) {
    const body = await response.text();
    const error = new ApiError(
      `${label} failed with ${response.status} ${response.statusText}`,
      response.status,
      body,
    );
    logApiError(label, error);
    throw error;
  }
  return await response.blob();
}

export async function requestVoid(
  url: string,
  init: RequestInit = {},
  label: string,
): Promise<void> {
  const response = await fetch(url, init);
  if (!response.ok) {
    const body = await response.text();
    const error = new ApiError(
      `${label} failed with ${response.status} ${response.statusText}`,
      response.status,
      body,
    );
    logApiError(label, error);
    throw error;
  }
}

/**
 * Shared fetch wrapper that handles try/catch, response.ok check, error logging, and fallback.
 *
 * For simple GET-and-return-JSON calls, pass only `url`, `init`, `fallback`, and `label`.
 * For calls needing custom hydration, pass a `transform` callback.
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
    logApiError(label, [response.status, response.statusText, await response.text()]);
  } catch (e) {
    logApiError(label, e);
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
  throwOnError = false,
  acceptedErrorStatuses: number[] = [],
): Promise<void> {
  try {
    const response = await fetch(url, init);
    if (!response.ok) {
      if (acceptedErrorStatuses.includes(response.status)) {
        return;
      }
      const body = await response.text();
      const details = [response.status, response.statusText, body];
      logApiError(label, details);
      if (throwOnError) {
        throw new ApiError(`${label} failed: ${details.join(" ")}`, response.status, body);
      }
    }
  } catch (e) {
    if (throwOnError) {
      throw e;
    }
    logApiError(label, e);
  }
}
