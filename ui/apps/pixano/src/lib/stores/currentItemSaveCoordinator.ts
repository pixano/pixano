/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

export type CurrentItemSaveStatus = "idle" | "saving" | "failed";
export type CurrentItemSaveResult = { ok: boolean };

export interface CurrentItemSaveState {
  isDirty: boolean;
  status: CurrentItemSaveStatus;
  errorMessage: string | null;
  activeRequestId: number | null;
}

export interface CurrentItemSaveCoordinatorController {
  readonly value: CurrentItemSaveState;
  syncDirty: (isDirty: boolean) => void;
  requestSave: () => Promise<CurrentItemSaveResult>;
  setSaveFailed: (message?: string, requestId?: number | null) => void;
  setSaveSucceeded: (requestId?: number | null, isDirty?: boolean) => void;
  resetForItemChange: () => void;
}

const DEFAULT_SAVE_ERROR_MESSAGE = "Save failed. Please try again.";

export function createInitialCurrentItemSaveState(): CurrentItemSaveState {
  return {
    isDirty: false,
    status: "idle",
    errorMessage: null,
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
      });
      return;
    }

    if (!isDirty) {
      commit({
        ...state,
        isDirty: false,
        status: "idle",
        errorMessage: null,
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
    if (pendingRequest) return pendingRequest.promise;

    if (!state.isDirty) {
      commit({
        ...state,
        status: "idle",
        errorMessage: null,
        activeRequestId: null,
      });
      return Promise.resolve({ ok: true });
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
      activeRequestId: requestId,
    });

    return promise;
  }

  function setSaveFailed(message = DEFAULT_SAVE_ERROR_MESSAGE, requestId = state.activeRequestId) {
    if (requestId == null) return;
    if (pendingRequest?.id !== requestId || state.activeRequestId !== requestId) return;

    commit({
      ...state,
      status: "failed",
      errorMessage: message,
      activeRequestId: null,
    });

    resolvePending({ ok: false }, requestId);
  }

  function setSaveSucceeded(requestId = state.activeRequestId, isDirty = false) {
    if (requestId == null) return;
    if (pendingRequest?.id !== requestId || state.activeRequestId !== requestId) return;

    commit({
      ...state,
      isDirty,
      status: "idle",
      errorMessage: null,
      activeRequestId: null,
    });

    resolvePending({ ok: !isDirty }, requestId);
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
    setSaveFailed,
    setSaveSucceeded,
    resetForItemChange,
  };
}
