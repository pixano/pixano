/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

/**
 * Svelte 5 runes-based document state (Phase 6b migration target).
 *
 * This module provides Svelte 5 rune equivalents for the store-based
 * DocumentStore. During migration, components can opt-in to runes
 * while the writable store versions continue to work.
 *
 * Usage (in a Svelte 5 component):
 *   import { createDocumentState } from '@pixano/store/runes/documentState';
 *   const state = createDocumentState(initialDocument);
 *   // state.document is reactive via $state
 *   // state.annotations is derived via $derived
 *
 * NOTE: This file requires Svelte 5 runes. It will cause a compile error
 * if imported in a Svelte 4 context. Only import after upgrading to Svelte 5.
 */

// This is a placeholder for the Svelte 5 migration.
// The actual implementation uses $state and $derived runes which require Svelte 5.
// It will be activated after the framework upgrade (Phase 6a).

export const SVELTE5_RUNES_PLACEHOLDER = true;

// Example of what the runes-based API will look like:
//
// import type { Document, AnnotationNode, NodeId } from '@pixano/document';
//
// export function createDocumentState(initialDocument: Document) {
//   let document = $state(initialDocument);
//   const annotations = $derived(document.getAnnotations());
//   let selectedIds = $state(new Set<NodeId>());
//
//   return {
//     get document() { return document; },
//     set document(doc: Document) { document = doc; },
//     get annotations() { return annotations; },
//     get selectedIds() { return selectedIds; },
//     set selectedIds(ids: Set<NodeId>) { selectedIds = ids; },
//     annotationsByView(viewName: string) {
//       return $derived(document.getAnnotationsByView(viewName));
//     },
//   };
// }
