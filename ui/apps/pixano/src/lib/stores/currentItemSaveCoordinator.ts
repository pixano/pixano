/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

export type CurrentItemSaveStatus = "idle" | "saving" | "failed";
export type CurrentItemSaveGuardMode = "armed" | "bypassed";
export type CurrentItemSaveResult = { ok: boolean };

export interface CurrentItemSaveState {
  isDirty: boolean;
  status: CurrentItemSaveStatus;
  errorMessage: string | null;
  guardMode: CurrentItemSaveGuardMode;
  activeRequestId: number | null;
}

export interface CurrentItemSaveCoordinatorController {
  readonly value: CurrentItemSaveState;
  syncDirty: (isDirty: boolean) => void;
  requestSave: () => Promise<CurrentItemSaveResult>;
  beginDiscardBypass: () => void;
  endDiscardBypass: () => void;
  setSaveFailed: (message?: string, requestId?: number | null) => void;
  setSaveSucceeded: (requestId?: number | null) => void;
  resetForItemChange: () => void;
}

const DEFAULT_SAVE_ERROR_MESSAGE = "Save failed. Please try again.";

export function createInitialCurrentItemSaveState(): CurrentItemSaveState {
  return {
    isDirty: false,
    status: "idle",
    errorMessage: null,
    guardMode: "armed",
    activeRequestId: null,
  };
}

export function createCurrentItemSaveCoordinatorController(
  onStateChange?: (state: CurrentItemSaveState) => void,
): CurrentItemSaveCoordinatorController {
  let state = createInitialCurrentItemSaveState();
  let nextRequestId = 1;
  let pendingRequest: {
    id: number;
    promise: Promise<CurrentItemSaveResult>;
    resolve: (result: CurrentItemSaveResult) => void;
  } | null = null;

  function commit(nextState: CurrentItemSaveState) {
    state = nextState;
    onStateChange?.(nextState);
  }

  function resolvePending(result: CurrentItemSaveResult, requestId?: number | null) {
    if (!pendingRequest) return;
    if (requestId != null && pendingRequest.id !== requestId) return;
    pendingRequest.resolve(result);
    pendingRequest = null;
  }

  function syncDirty(isDirty: boolean) {
    if (pendingRequest) {
      commit({
        ...state,
        isDirty,
        guardMode: isDirty ? state.guardMode : "armed",
      });
      return;
    }

    if (!isDirty) {
      commit({
        ...state,
        isDirty: false,
        status: "idle",
        errorMessage: null,
        guardMode: "armed",
        activeRequestId: null,
      });
      return;
    }

    commit({
      ...state,
      isDirty: true,
    });
  }

  function requestSave(): Promise<CurrentItemSaveResult> {
    if (!state.isDirty) {
      commit({
        ...state,
        status: "idle",
        errorMessage: null,
        guardMode: "armed",
        activeRequestId: null,
      });
      return Promise.resolve({ ok: true });
    }

    if (pendingRequest) {
      return pendingRequest.promise;
    }

    const requestId = nextRequestId++;
    let resolvePromise!: (result: CurrentItemSaveResult) => void;

    const promise = new Promise<CurrentItemSaveResult>((resolve) => {
      resolvePromise = resolve;
    });

    pendingRequest = {
      id: requestId,
      promise,
      resolve: resolvePromise,
    };

    commit({
      ...state,
      status: "saving",
      errorMessage: null,
      guardMode: "armed",
      activeRequestId: requestId,
    });

    return promise;
  }

  function beginDiscardBypass() {
    commit({
      ...state,
      guardMode: "bypassed",
    });
  }

  function endDiscardBypass() {
    commit({
      ...state,
      guardMode: "armed",
    });
  }

  function setSaveFailed(message = DEFAULT_SAVE_ERROR_MESSAGE, requestId = state.activeRequestId) {
    if (requestId == null) return;
    if (pendingRequest && pendingRequest.id !== requestId) return;

    commit({
      ...state,
      status: "failed",
      errorMessage: message,
      guardMode: "armed",
      activeRequestId: null,
    });

    resolvePending({ ok: false }, requestId);
  }

  function setSaveSucceeded(requestId = state.activeRequestId) {
    if (requestId == null) return;
    if (pendingRequest && pendingRequest.id !== requestId) return;

    commit({
      ...state,
      isDirty: false,
      status: "idle",
      errorMessage: null,
      guardMode: "armed",
      activeRequestId: null,
    });

    resolvePending({ ok: true }, requestId);
  }

  function resetForItemChange() {
    resolvePending({ ok: false });
    commit(createInitialCurrentItemSaveState());
  }

  return {
    get value() {
      return state;
    },
    syncDirty,
    requestSave,
    beginDiscardBypass,
    endDiscardBypass,
    setSaveFailed,
    setSaveSucceeded,
    resetForItemChange,
  };
}
