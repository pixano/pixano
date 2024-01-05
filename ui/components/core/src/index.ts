/**
 * @copyright CEA
 * @author CEA
 * @license CECILL
 *
 * This software is a collaborative computer program whose purpose is to
 * generate and explore labeled data for computer vision applications.
 * This software is governed by the CeCILL-C license under French law and
 * abiding by the rules of distribution of free software. You can use,
 * modify and/ or redistribute the software under the terms of the CeCILL-C
 * license as circulated by CEA, CNRS and INRIA at the following URL
 *
 * http://www.cecill.info
 */

// Exports
export * from "./lib/types";
export * as api from "./api";
export * as icons from "./icons";
export * as utils from "./utils";

// Modals
export { default as ConfirmModal } from "./components/modals/ConfirmModal.svelte";
export { default as LoadingModal } from "./components/modals/LoadingModal.svelte";
export { default as PromptModal } from "./components/modals/PromptModal.svelte";
export { default as SelectModal } from "./components/modals/SelectModal.svelte";
export { default as WarningModal } from "./components/modals/WarningModal.svelte";

export { default as Histogram } from "./components/Histogram.svelte";
