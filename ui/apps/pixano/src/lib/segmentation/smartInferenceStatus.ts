/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { ApiError } from "$lib/api/apiClient";
import type { SmartSegmentationUiState } from "$lib/types/workspace";

const DEFAULT_ERROR_MESSAGE = "Segmentation failed. Click again to retry or press Esc to clear.";

function truncateMessage(message: string, maxLength = 220): string {
  if (message.length <= maxLength) return message;
  return `${message.slice(0, maxLength - 1).trimEnd()}…`;
}

function extractStructuredDetail(value: unknown): string | null {
  if (typeof value === "string" && value.trim().length > 0) {
    return value.trim();
  }

  if (Array.isArray(value) && value.length > 0) {
    const details = value
      .map((entry) => extractStructuredDetail(entry))
      .filter((entry): entry is string => Boolean(entry));
    return details.length > 0 ? details.join(" ") : null;
  }

  if (value && typeof value === "object") {
    if ("detail" in value) {
      return extractStructuredDetail((value as { detail?: unknown }).detail);
    }

    if ("msg" in value) {
      return extractStructuredDetail((value as { msg?: unknown }).msg);
    }
  }

  return null;
}

export function createIdleSmartSegmentationUiState(): SmartSegmentationUiState {
  return {
    phase: "idle",
    requestId: null,
    viewName: null,
    message: "",
  };
}

export function createPendingSmartSegmentationUiState(
  requestId: string,
  viewName: string,
): SmartSegmentationUiState {
  return {
    phase: "pending",
    requestId,
    viewName,
    message: "Running segmentation...",
  };
}

export function getSmartSegmentationErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    const body = error.body.trim();
    if (body) {
      try {
        const parsed = JSON.parse(body) as unknown;
        const detail = extractStructuredDetail(parsed);
        if (detail) {
          return truncateMessage(`Segmentation failed. ${detail}`);
        }
      } catch {
        return truncateMessage(`Segmentation failed. ${body}`);
      }
    }

    return truncateMessage(`Segmentation failed. ${error.message}`);
  }

  if (error instanceof Error && error.message.trim().length > 0) {
    return truncateMessage(`Segmentation failed. ${error.message.trim()}`);
  }

  return DEFAULT_ERROR_MESSAGE;
}

export function createErrorSmartSegmentationUiState(
  requestId: string,
  viewName: string,
  error: unknown,
): SmartSegmentationUiState {
  return {
    phase: "error",
    requestId,
    viewName,
    message: getSmartSegmentationErrorMessage(error),
  };
}
