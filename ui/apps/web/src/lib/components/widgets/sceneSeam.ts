/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { ViewScopedAnnotations } from "$lib/annotations/annotationCollection.svelte.js";
import type { BuildContext } from "$lib/annotations/buildPayloads.js";
import type { MutationSink, SeamContext } from "$lib/annotations/scene/sceneContext.js";
import type { WorkspaceManager } from "$lib/workspace/workspaceManager.svelte.js";

/**
 * The mutation half of a scene's seam: a narrow `MutationSink` that forwards to
 * the shared `WorkspaceManager` queue. Identical for every widget, so it lives
 * here instead of being re-declared inline in each host (Image, PointCloud, …).
 */
export function buildMutationSink(manager: WorkspaceManager): MutationSink {
  return {
    get pending() {
      return manager.pendingMutations;
    },
    queue: (m) => manager.queueMutation(m),
    upsertUpdate: (m) => manager.upsertUpdateMutation(m),
    patchPendingCreate: (id, resource, patch) =>
      manager.patchPendingCreateMutation(id, resource, patch),
    dropForLocalAnnotation: (id) => void manager.dropMutationsForLocalAnnotation(id),
    dropPendingEntityCreate: (id) => manager.dropPendingEntityCreate(id),
  };
}

/**
 * Build the medium-agnostic scene seam every widget shares: a view-scoped
 * window onto the record's collection, the mutation sink, the tool switcher and
 * the redraw hook. A 2D / 3D / text host calls this once, then completes the
 * seam with its own engine handles (a Konva stage, a Threlte camera, an editor
 * DOM node, …). This is the single entry point a new medium reuses — adding one
 * never re-implements collection wiring or mutation plumbing.
 */
export function buildSeam(
  manager: WorkspaceManager,
  opts: {
    widgetId: string;
    buildContext: BuildContext;
    storage: { activeToolId: string };
    requestRedraw?: () => void;
  },
): SeamContext {
  return {
    widgetId: opts.widgetId,
    buildContext: opts.buildContext,
    collection: new ViewScopedAnnotations(() => manager.annotations, opts.buildContext.viewId),
    mutations: buildMutationSink(manager),
    // The live-draft slot is shared workspace-wide, so ownership is enforced
    // here rather than left to each tool: `publish` stamps this widget's id, and
    // `clear` only ever clears a draft this widget published. A tool physically
    // cannot wipe a gesture running in another widget.
    liveDraft: {
      get: () => manager.liveDraft,
      publish: (draft) => manager.setLiveDraft({ ...draft, sourceWidgetId: opts.widgetId }),
      clear: () => {
        if (manager.liveDraft?.sourceWidgetId === opts.widgetId) manager.setLiveDraft(null);
      },
    },
    setActiveTool: (id) => {
      opts.storage.activeToolId = id;
    },
    requestRedraw: opts.requestRedraw ?? (() => {}),
    beginPendingAnnotation: (pending) => manager.beginPendingAnnotation(pending),
    findEntity: (entityId) => manager.entities.find((e) => e.id === entityId),
    isEntityVisible: (entityId) => manager.isEntityVisible(entityId),
  };
}
