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
  params: Record<string, string | number | boolean | null | undefined>,
): string {
  const searchParams = new URLSearchParams();

  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") {
      continue;
    }
    searchParams.set(key, String(value));
  }

  const query = searchParams.toString();
  return query ? `?${query}` : "";
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
      const details = [response.status, response.statusText, await response.text()];
      logApiError(label, details);
      if (throwOnError) {
        throw new Error(`${label} failed: ${details.join(" ")}`);
      }
    }
  } catch (e) {
    if (throwOnError) {
      throw e;
    }
    logApiError(label, e);
  }
}
