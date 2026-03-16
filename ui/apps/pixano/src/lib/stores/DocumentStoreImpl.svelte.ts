/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { AnnotationNode, Document, NodeId } from "$lib/document";
import type { DocumentStore, ReactiveReadonly, ReactiveValue } from "$lib/types/store";

/**
 * Reactive store wrapping a Document snapshot.
 *
 * The document itself is set by the CommandBridge after each command.
 * All derived getters automatically update when the document changes.
 */
export class DocumentStoreImpl implements DocumentStore {
  private _doc = $state<Document>(undefined as unknown as Document);
  private _selectedIds = $state<Set<NodeId>>(new Set());

  // Cache for per-view derived getters
  private readonly viewGetters = new Map<string, ReactiveReadonly<ReadonlyArray<AnnotationNode>>>();

  readonly document: ReactiveReadonly<Document> = {
    get value() {
      return undefined as unknown as Document;
    },
  };

  readonly annotations: ReactiveReadonly<ReadonlyArray<AnnotationNode>> = {
    get value() {
      return [] as ReadonlyArray<AnnotationNode>;
    },
  };

  readonly selectedIds: ReactiveValue<Set<NodeId>>;

  constructor(initialDocument: Document) {
    this._doc = initialDocument;

    // eslint-disable-next-line @typescript-eslint/no-this-alias
    const self = this;
    this.document = {
      get value() {
        return self._doc;
      },
    };
    this.annotations = {
      get value() {
        return self._doc.getAnnotations();
      },
    };
    this.selectedIds = {
      get value() {
        return self._selectedIds;
      },
      set value(v: Set<NodeId>) {
        self._selectedIds = v;
      },
      update(fn: (prev: Set<NodeId>) => Set<NodeId>) {
        self._selectedIds = fn(self._selectedIds);
      },
    };
  }

  annotationsByView(viewName: string): ReactiveReadonly<ReadonlyArray<AnnotationNode>> {
    let getter = this.viewGetters.get(viewName);
    if (!getter) {
      // eslint-disable-next-line @typescript-eslint/no-this-alias
      const self = this;
      getter = {
        get value() {
          return self._doc.getAnnotationsByView(viewName);
        },
      };
      this.viewGetters.set(viewName, getter);
    }
    return getter;
  }

  /** Called by CommandBridge to update the document after a command. */
  setDocument(doc: Document): void {
    this._doc = doc;
  }

  /** Get current document value (non-reactive). */
  getCurrentDocument(): Document {
    return this._doc;
  }
}
