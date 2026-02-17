/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { derived, writable, type Readable, type Writable } from "svelte/store";

import type { AnnotationNode, Document, NodeId } from "@pixano/document";

import type { DocumentStore } from "../types";

/**
 * Reactive Svelte store wrapping a Document snapshot.
 *
 * The document itself is set by the CommandBridge after each command.
 * All derived stores automatically update when the document changes.
 */
export class DocumentStoreImpl implements DocumentStore {
  private readonly _document: Writable<Document>;

  readonly document: Readable<Document>;
  readonly annotations: Readable<ReadonlyArray<AnnotationNode>>;
  readonly selectedIds: Writable<Set<NodeId>>;

  // Cache for per-view derived stores
  private readonly viewStores = new Map<string, Readable<ReadonlyArray<AnnotationNode>>>();

  constructor(initialDocument: Document) {
    this._document = writable(initialDocument);
    this.document = { subscribe: this._document.subscribe };

    this.annotations = derived(this._document, ($doc) => $doc.getAnnotations());

    this.selectedIds = writable(new Set<NodeId>());
  }

  annotationsByView(viewName: string): Readable<ReadonlyArray<AnnotationNode>> {
    let store = this.viewStores.get(viewName);
    if (!store) {
      store = derived(this._document, ($doc) => $doc.getAnnotationsByView(viewName));
      this.viewStores.set(viewName, store);
    }
    return store;
  }

  /** Called by CommandBridge to update the document after a command. */
  setDocument(doc: Document): void {
    this._document.set(doc);
  }

  /** Get current document value (non-reactive). */
  getCurrentDocument(): Document {
    let current: Document | undefined;
    this._document.subscribe((d) => (current = d))();
    return current!;
  }
}
