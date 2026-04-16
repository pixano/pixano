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
