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

/** The first HTTP status of a refusal (4xx): the server applied nothing. */
const FIRST_CLIENT_ERROR_STATUS = 400;
/** The first HTTP status of a server failure (5xx): it may have applied the request. */
const FIRST_SERVER_ERROR_STATUS = 500;

/**
 * Whether a request failed because the server refused it, and so applied
 * nothing: an `ApiError` with a 4xx status. A network error, a lost answer or
 * a 5xx tells nothing of the kind — the request may have been applied.
 */
export function isRefusal(err: unknown): boolean {
  return (
    err instanceof ApiError &&
    err.status >= FIRST_CLIENT_ERROR_STATUS &&
    err.status < FIRST_SERVER_ERROR_STATUS
  );
}

/**
 * The error a failed answer stands for: its status and its body, so that a
 * caller can tell a refusal (`isRefusal`) and show the server's reason.
 */
export async function apiErrorFrom(response: Response, label: string): Promise<ApiError> {
  const body = await response.text();
  return new ApiError(
    `${label} failed with ${response.status} ${response.statusText}`,
    response.status,
    body,
  );
}

function logApiError(label: string, error: unknown): void {
  console.error(`api.${label} -`, error);
}

export async function requestJson<T>(
  url: string,
  init: RequestInit = {},
  label: string,
): Promise<T> {
  const response = await fetch(url, init);
  if (!response.ok) {
    const error = await apiErrorFrom(response, label);
    logApiError(label, error);
    throw error;
  }
  return (await response.json()) as T;
}

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
