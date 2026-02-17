/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { Document, NodeId } from "@pixano/document";
import type { ToolEvent } from "@pixano/tools";

/**
 * Abstract renderer adapter interface.
 *
 * Both 2D (Konva) and 3D (Threlte) renderers implement this interface,
 * enabling multi-view layouts with coordinated selection.
 */
export interface RendererAdapter {
  /** Mount the renderer into a container element. */
  mount(container: HTMLElement): void;

  /** Unmount and clean up. */
  unmount(): void;

  /** Update the displayed document. */
  setDocument(document: Document): void;

  /** Highlight/select specific nodes. */
  setSelection(selectedIds: ReadonlySet<NodeId>): void;

  /** Forward a tool event to the renderer (e.g., for hit-testing). */
  onToolEvent(event: ToolEvent): void;

  /** Get the view name this renderer is displaying. */
  getViewName(): string;
}
