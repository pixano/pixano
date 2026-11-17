/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

/**
 * Detection in the image workspace: the inspector panel's session (`detectionSession`), the run,
 * and what the panel shows. A run sends the class and/or the exemplars of the current view, and
 * stages one object and one box per new proposal, a model's rows the review mode then accepts or
 * rejects. Persisting is the workspace's normal save.
 */

import {
  beginRunState,
  closeState,
  completeRunState,
  failRunState,
  isDetectionActiveState,
  NULL_DETECTION_STATE,
  openSetupState,
  resetState,
  selectViewState,
  updateParamsState,
  type DetectionSessionState,
  type DetectionTarget,
} from "./detectionSession";
import { reactiveDerived, reactiveStore } from "./reactiveStore.svelte";
import {
  annotations,
  entities,
  itemMetas,
  selectedTool,
  views,
} from "./workspaceBaseStores.svelte";
import { ApiError } from "$lib/api/apiClient";
import { detectObjects } from "$lib/api/inferenceApi";
import {
  bboxesOfView,
  bboxToPixelBox,
  buildDetectionRequest,
  collectExemplars,
  collectNegatives,
  filterProposals,
  type DetectionImage,
  type DetectionParams,
  type PixelBox,
} from "$lib/detection/detection";
import { buildDetectionRows } from "$lib/detection/detectionRows";
import { detectionExampleTool, panTool } from "$lib/tools";
import type { BBox, FeaturesValues, Image, ItemFeature } from "$lib/types/dataset";
import {
  supportsExemplars,
  supportsNegativeExemplars,
  type DetectionTaskInput,
  type DetectionTaskResult,
  type InferenceModel,
} from "$lib/types/inference";
import type { SaveRectangleShape } from "$lib/types/shapeTypes";
import type { SelectionTool } from "$lib/types/tools";
import { defineCreatedAnnotation, findOrCreateEntity } from "$lib/utils/entityOperations";
import { addNewInput } from "$lib/utils/featureMapping";
import { saveTo } from "$lib/utils/saveItemUtils";
import { resolveEntityLabelField } from "$lib/utils/workspaceDefaultFeatures";
import { commitNormalizedWorkspaceRuntime } from "$lib/utils/workspaceRuntimeMutations";
import type { WorkspaceManifest } from "$lib/workspace/manifest";

export type { DetectionSessionState } from "./detectionSession";

let detect: (input: DetectionTaskInput) => Promise<DetectionTaskResult> = detectObjects;

/** Tests inject the API call; `null` restores the real one. */
export function setDetectionApi(next: typeof detectObjects | null): void {
  detect = next ?? detectObjects;
}

export const detectionSession = reactiveStore<DetectionSessionState>({ ...NULL_DETECTION_STATE });

// ─── Views ──────────────────────────────────────────────────────────────────

/** The still images of the record, by view name, with what a run needs of them. */
export function resolveDetectionImages(): DetectionImage[] {
  return Object.entries(views.value)
    .filter(([, view]) => !Array.isArray(view))
    .map(([viewName, view]) => {
      const image = view as Image;
      return {
        viewId: image.id,
        viewName,
        width: Number(image.data?.width),
        height: Number(image.data?.height),
      };
    });
}

function resolveImage(viewName: string | null): DetectionImage | null {
  if (!viewName) return null;
  return resolveDetectionImages().find((image) => image.viewName === viewName) ?? null;
}

/** The entity field that holds the object label in this dataset, if any. */
export function resolveDetectionLabelField(manifest: WorkspaceManifest): string | null {
  const entityTable = manifest.tablesByGroup.entities[0];
  if (!entityTable) return null;
  return resolveEntityLabelField(Object.keys(manifest.tablesByName[entityTable]?.fields ?? {}));
}

// ─── Actions ────────────────────────────────────────────────────────────────

export function openDetectionSetup(target: DetectionTarget, viewName: string): void {
  selectedTool.value = panTool;
  detectionSession.update((state) => openSetupState(state, target, viewName));
}

export function selectDetectionView(viewName: string): void {
  detectionSession.update((state) => selectViewState(state, viewName));
}

export function updateDetectionParams(patch: Partial<DetectionParams>): void {
  detectionSession.update((state) => updateParamsState(state, patch));
}

export function closeDetectionSession(): void {
  stopAddingDetectionExamples();
  detectionSession.update(closeState);
}

// ─── Examples ───────────────────────────────────────────────────────────────

/**
 * Whether a tool is the example tool. By its fields, not identity: the tool store wraps the value it
 * holds in a proxy, which is never `===` the preset.
 */
export function isDetectionExampleTool(tool: SelectionTool | null | undefined): boolean {
  return tool?.type === detectionExampleTool.type && tool.autoConfirm === true;
}

/** Whether boxes drawn now are saved at once as examples of the panel's class. */
export const isAddingDetectionExamples = reactiveDerived(
  () =>
    isDetectionExampleTool(selectedTool.value) && isDetectionActiveState(detectionSession.value),
);

export function startAddingDetectionExamples(): void {
  if (!detectionSession.value.params.className.trim()) return;
  selectedTool.value = detectionExampleTool;
}

export function stopAddingDetectionExamples(): void {
  if (isDetectionExampleTool(selectedTool.value)) selectedTool.value = panTool;
}

export interface DetectionExampleContext {
  manifest: WorkspaceManifest;
  featureValues: FeaturesValues | undefined;
}

/**
 * Save a box drawn in example mode as a person's annotation: a new object whose label field holds
 * the panel's class, so that the next run counts it as an example. Returns the box, or `null` when
 * the shape is not one to take (no class, not a box).
 */
export function addDetectionExample(
  shape: SaveRectangleShape,
  context: DetectionExampleContext,
): BBox | null {
  const className = detectionSession.value.params.className.trim();
  if (!className || !(shape.attrs.width > 0 && shape.attrs.height > 0)) return null;
  const labelField = resolveDetectionLabelField(context.manifest);
  const entityTable = context.manifest.tablesByGroup.entities[0] ?? "entities";
  const features: Record<string, ItemFeature> = labelField
    ? { [labelField]: { name: labelField, dtype: "str", value: className } }
    : {};
  const entity = findOrCreateEntity("new", shape, { [entityTable]: features }, context.manifest);
  const bbox = defineCreatedAnnotation(
    entity,
    { [entityTable]: features },
    shape,
    shape.viewRef,
    context.manifest,
    false,
    -1,
  ) as BBox | undefined;
  if (!bbox) return null;
  if (itemMetas.value?.type) bbox.ui.datasetItemType = itemMetas.value.type;
  bbox.ui.displayControl = { hidden: false, editing: false, highlighted: "all" };
  bbox.ui.top_entities = [entity];
  entity.ui.childs = [bbox];
  saveTo("add", entity);
  saveTo("add", bbox);
  commitNormalizedWorkspaceRuntime([...annotations.value, bbox], [...entities.value, entity]);
  if (labelField) addNewInput(context.featureValues, "objects", labelField, className);
  return bbox;
}

export function resetDetectionSession(): void {
  detectionSession.update(resetState);
}

function describeError(error: unknown): string {
  if (error instanceof ApiError) {
    try {
      const body = JSON.parse(error.body) as { detail?: string | { message?: string } };
      const detail = typeof body.detail === "string" ? body.detail : body.detail?.message;
      if (detail) return detail;
    } catch {
      // Not JSON: fall through to the generic message.
    }
    return `Detection failed (${error.status}).`;
  }
  return error instanceof Error ? error.message : "Detection failed.";
}

export interface DetectionRunContext {
  model: InferenceModel;
  manifest: WorkspaceManifest;
  featureValues: FeaturesValues | undefined;
}

export interface DetectionRunResult {
  added: number;
}

/**
 * Run the model on the session's view and stage its new proposals. Returns what was added, or
 * `null` when nothing was (refused, failed, or superseded: the session says why).
 */
export async function runDetection(
  context: DetectionRunContext,
): Promise<DetectionRunResult | null> {
  const state = detectionSession.value;
  const image = resolveImage(state.viewName);
  if (!state.target || !image || state.phase === "running" || state.phase === "closed") return null;
  const target = state.target;
  const requestId = `detection-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
  detectionSession.update((current) => beginRunState(current, requestId));
  const fail = (message: string): null => {
    detectionSession.update((current) => failRunState(current, requestId, message));
    return null;
  };

  if (!(image.width > 0 && image.height > 0)) {
    return fail("The size of this image is unknown; the boxes could not be placed.");
  }
  const labelField = resolveDetectionLabelField(context.manifest);
  const exemplars = collectExemplars({
    annotations: annotations.value,
    entities: entities.value,
    image,
    labelField,
    className: state.params.className,
  });
  const negatives = collectNegatives(state.proposals, annotations.value, image.viewName);
  const readsExemplars = supportsExemplars(context.model);
  const request = buildDetectionRequest({
    model: context.model.name,
    providerName: context.model.provider_name,
    datasetId: target.datasetId,
    image,
    params: state.params,
    exemplars,
    negatives,
    readsExemplars,
    readsNegatives: supportsNegativeExemplars(context.model),
  });
  if (!request) {
    return fail(
      readsExemplars
        ? "Name a class, or box a few objects first."
        : "Name a class: this model does not take example boxes.",
    );
  }

  let result: DetectionTaskResult;
  try {
    result = await detect(request);
  } catch (error) {
    return fail(describeError(error));
  }
  const current = detectionSession.value;
  if (current.requestId !== requestId || current.target?.recordId !== target.recordId) return null;

  // Every box already on the view, proposals still to review included, and every proposal
  // rejected on it: none is proposed twice, whatever the model makes of the negatives.
  const existing = [
    ...bboxesOfView(annotations.value, image.viewName)
      .map((bbox) => bboxToPixelBox(bbox, image.width, image.height))
      .filter((box): box is PixelBox => box !== null),
    ...collectNegatives(current.proposals, annotations.value, image.viewName),
  ];
  const { proposals, duplicates } = filterProposals(result.data, existing, image);
  const className = current.params.className.trim();
  const rows = buildDetectionRows({
    proposals,
    itemId: target.recordId,
    image,
    manifest: context.manifest,
    labelField,
    className,
    source: { modelName: context.model.name, providerName: context.model.provider_name },
    prompt: {
      text: (request.classes?.length ?? 0) > 0,
      exemplars: request.exemplar_boxes?.length ?? 0,
      negatives: request.negative_exemplar_boxes?.length ?? 0,
    },
    workspaceType: itemMetas.value?.type,
  });

  for (const entity of rows.entities) saveTo("add", entity);
  for (const bbox of rows.bboxes) saveTo("add", bbox);
  if (rows.bboxes.length > 0) {
    commitNormalizedWorkspaceRuntime(
      [...annotations.value, ...rows.bboxes],
      [...entities.value, ...rows.entities],
    );
    if (labelField && className)
      addNewInput(context.featureValues, "objects", labelField, className);
  }
  detectionSession.update((latest) =>
    completeRunState(
      latest,
      requestId,
      rows.bboxes.map((bbox, index) => ({
        bboxId: bbox.id,
        viewName: image.viewName,
        box: rows.proposals[index].box,
      })),
      {
        found: result.data.boxes.length,
        added: rows.bboxes.length,
        duplicates,
        exemplars: request.exemplar_boxes?.length ?? 0,
        negatives: request.negative_exemplar_boxes?.length ?? 0,
      },
    ),
  );
  return { added: rows.bboxes.length };
}

// ─── Derived ────────────────────────────────────────────────────────────────

export const isDetectionActive = reactiveDerived(() =>
  isDetectionActiveState(detectionSession.value),
);
