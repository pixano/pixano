/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { IconProps } from "lucide-svelte";
import type { ComponentType, SvelteComponent } from "svelte";

import type { AnnotationKind } from "../annotationCollection.svelte.js";

/**
 * Metadata shared by every tool, 2D or 3D — the tool-level type the two scene
 * families have in common (docs/ARCHITECTURE_TOOLING.md, decision D3).
 */
export interface ToolDefinition {
  /** Unique id, e.g. "select", "draw-bbox". */
  id: string;
  /** Toolbar tooltip text. */
  label: string;
  /** Lucide icon component rendered in the toolbar. */
  icon: ComponentType<SvelteComponent<IconProps>>;
  /** Annotation kind this tool produces; omitted for kind-agnostic tools. */
  kind?: AnnotationKind;
  /** CSS cursor applied to the canvas while the tool is active. */
  cursor?: string;
}
