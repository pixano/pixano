/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import {
  createCurrentItemSaveCoordinatorController,
  createInitialCurrentItemSaveState,
  type CurrentItemSaveCoordinatorController,
  type CurrentItemSaveResult,
  type CurrentItemSaveState,
  type CurrentItemSaveStatus,
} from "./currentItemSaveCoordinator";
import { reactiveStore } from "./reactiveStore.svelte";

export type { CurrentItemSaveResult, CurrentItemSaveState, CurrentItemSaveStatus };

export interface CurrentItemSaveCoordinator {
  readonly value: CurrentItemSaveState;
  syncDirty: (isDirty: boolean) => void;
  requestSave: () => Promise<CurrentItemSaveResult>;
  setSaveFailed: CurrentItemSaveCoordinatorController["setSaveFailed"];
  setSaveSucceeded: CurrentItemSaveCoordinatorController["setSaveSucceeded"];
  resetForItemChange: () => void;
}

export function createCurrentItemSaveCoordinator(): CurrentItemSaveCoordinator {
  const state = reactiveStore<CurrentItemSaveState>(createInitialCurrentItemSaveState());
  const controller = createCurrentItemSaveCoordinatorController((nextState) => {
    state.value = nextState;
  });

  state.value = controller.value;

  return {
    get value() {
      return state.value;
    },
    syncDirty: controller.syncDirty,
    requestSave: controller.requestSave,
    setSaveFailed: controller.setSaveFailed,
    setSaveSucceeded: controller.setSaveSucceeded,
    resetForItemChange: controller.resetForItemChange,
  };
}
