/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

/**
 * The detection session of the image workspace, as a pure reducer: the panel's form, the run in
 * flight, and the proposals the session added to the record, from which the proposals since
 * rejected are found again (`collectNegatives`). The proposals are kept while the session moves
 * between views of the record, and while the panel is closed, and dropped with the record.
 */

import {
  DEFAULT_DETECTION_PARAMS,
  type DetectionParams,
  type SessionProposal,
} from "$lib/detection/detection";

export type DetectionPhase = "closed" | "setup" | "running" | "error";

export interface DetectionTarget {
  datasetId: string;
  recordId: string;
}

export interface DetectionRunSummary {
  /** Detections the model returned. */
  found: number;
  /** Proposals added to the image. */
  added: number;
  /** Detections dropped as boxes already on the image. */
  duplicates: number;
  exemplars: number;
  negatives: number;
}

export interface DetectionSessionState {
  phase: DetectionPhase;
  target: DetectionTarget | null;
  viewName: string | null;
  params: DetectionParams;
  requestId: string | null;
  proposals: SessionProposal[];
  lastRun: DetectionRunSummary | null;
  error: string | null;
}

export const NULL_DETECTION_STATE: DetectionSessionState = {
  phase: "closed",
  target: null,
  viewName: null,
  params: { ...DEFAULT_DETECTION_PARAMS },
  requestId: null,
  proposals: [],
  lastRun: null,
  error: null,
};

export function isDetectionActiveState(state: DetectionSessionState): boolean {
  return state.phase !== "closed";
}

function sameRecord(left: DetectionTarget | null, right: DetectionTarget): boolean {
  return left?.datasetId === right.datasetId && left?.recordId === right.recordId;
}

/** Open the form on a view. Another record starts afresh, the parameters aside. */
export function openSetupState(
  state: DetectionSessionState,
  target: DetectionTarget,
  viewName: string,
): DetectionSessionState {
  const keep = sameRecord(state.target, target);
  return {
    ...state,
    phase: "setup",
    target,
    viewName,
    requestId: null,
    proposals: keep ? state.proposals : [],
    lastRun: keep ? state.lastRun : null,
    error: null,
  };
}

export function selectViewState(
  state: DetectionSessionState,
  viewName: string,
): DetectionSessionState {
  if (state.phase === "running" || state.viewName === viewName) return state;
  return { ...state, viewName, lastRun: null, error: null, phase: "setup" };
}

export function updateParamsState(
  state: DetectionSessionState,
  patch: Partial<DetectionParams>,
): DetectionSessionState {
  return { ...state, params: { ...state.params, ...patch } };
}

export function beginRunState(
  state: DetectionSessionState,
  requestId: string,
): DetectionSessionState {
  if (state.phase === "closed" || state.phase === "running") return state;
  return { ...state, phase: "running", requestId, error: null };
}

/** A run's result; a run superseded or cancelled since is ignored. */
export function completeRunState(
  state: DetectionSessionState,
  requestId: string,
  added: readonly SessionProposal[],
  summary: DetectionRunSummary,
): DetectionSessionState {
  if (state.phase !== "running" || state.requestId !== requestId) return state;
  return {
    ...state,
    phase: "setup",
    requestId: null,
    proposals: [...state.proposals, ...added],
    lastRun: summary,
  };
}

export function failRunState(
  state: DetectionSessionState,
  requestId: string,
  message: string,
): DetectionSessionState {
  if (state.requestId !== requestId) return state;
  return { ...state, phase: "error", requestId: null, error: message };
}

/** Close the panel; the record's proposals stay known, so a later run still finds the rejected ones. */
export function closeState(state: DetectionSessionState): DetectionSessionState {
  return { ...state, phase: "closed", requestId: null, error: null };
}

/** Forget the record: another one is open. */
export function resetState(state: DetectionSessionState): DetectionSessionState {
  return { ...NULL_DETECTION_STATE, params: { ...state.params } };
}
