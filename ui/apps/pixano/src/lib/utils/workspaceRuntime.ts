/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import {
  Annotation,
  BaseSchema,
  Entity,
  entityHasTracklets,
  initDisplayControl,
  isSequenceFrameArray,
  Mask,
  Tracklet,
  WorkspaceType,
  type View,
} from "$lib/types/dataset";
import { tryGetTopEntityFromList } from "$lib/utils/entityLookupUtils";
import {
  resolveMaskBitmapSource,
  resolveMaskBounds,
  rleCountsToBounds,
  rleFrString,
} from "$lib/utils/maskUtils";
import { sortByFrameIndex } from "$lib/utils/videoUtils";

type MView = Record<string, View | View[]>;

export interface WorkspaceRuntimeSnapshot {
  annotations: Annotation[];
  entities: Entity[];
}

function ensureAnnotationRuntimeFields(
  annotation: Annotation,
  workspaceType: WorkspaceType,
  views: MView,
): Annotation {
  const currentUi = annotation.ui ?? {
    datasetItemType: workspaceType,
    displayControl: { ...initDisplayControl },
  };
  annotation.ui = {
    ...currentUi,
    datasetItemType: workspaceType,
    displayControl: currentUi.displayControl ?? { ...initDisplayControl },
  };

  if (annotation.is_type(BaseSchema.Mask)) {
    const mask = annotation as Mask;
    if (!mask.ui.bitmapUrl) {
      mask.ui.bitmapUrl =
        resolveMaskBitmapSource({ data: mask.data, metadata: mask.data.inference_metadata }) ??
        undefined;
    }
    if (!mask.ui.bounds) {
      mask.ui.bounds =
        resolveMaskBounds({ data: mask.data, metadata: mask.data.inference_metadata }) ?? undefined;
    }
    if (!mask.ui.bounds) {
      if (typeof mask.data.counts === "string") {
        mask.data.counts = rleFrString(mask.data.counts);
      }
      if (Array.isArray(mask.data.counts) && mask.data.size.length >= 2) {
        const h = mask.data.size[0];
        const w = mask.data.size[1];
        if (Number.isFinite(h) && Number.isFinite(w) && h > 0 && w > 0) {
          mask.ui.bounds = rleCountsToBounds(mask.data.counts, [h, w]) ?? undefined;
        }
      }
    }
  }

  if (workspaceType !== WorkspaceType.VIDEO || annotation.is_type(BaseSchema.Tracklet)) {
    return annotation;
  }

  const dataFrameIndex = annotation.data.frame_index;
  if (typeof dataFrameIndex === "number" && dataFrameIndex >= 0) {
    annotation.ui.frame_index = dataFrameIndex;
    return annotation;
  }

  const frameId = annotation.data.frame_id;
  const viewName = annotation.data.view_name;
  if (
    typeof frameId !== "string" ||
    frameId === "" ||
    typeof viewName !== "string" ||
    viewName === ""
  ) {
    return annotation;
  }

  const candidateView = views[viewName];
  if (!candidateView || !isSequenceFrameArray(candidateView)) {
    return annotation;
  }
  const frame = candidateView.find((item) => item.id === frameId);
  if (frame) {
    annotation.data.frame_index = frame.data.frame_index;
    annotation.ui.frame_index = frame.data.frame_index;
  }
  return annotation;
}

function rebuildEntityChildren(entities: Entity[], annotations: Annotation[]): Entity[] {
  const childsByEntityId = new Map<string, Annotation[]>();
  for (const annotation of annotations) {
    const bucket = childsByEntityId.get(annotation.data.entity_id);
    if (bucket) {
      bucket.push(annotation);
    } else {
      childsByEntityId.set(annotation.data.entity_id, [annotation]);
    }
  }

  const subEntitiesChilds = new Map<string, Annotation[]>();
  for (const entity of entities) {
    const directChilds = childsByEntityId.get(entity.id) ?? [];
    entity.ui = {
      ...entity.ui,
      childs: directChilds,
    };
    if (entity.data.parent_id !== "" && directChilds.length > 0) {
      const existing = subEntitiesChilds.get(entity.data.parent_id) ?? [];
      subEntitiesChilds.set(entity.data.parent_id, existing.concat(directChilds));
    }
  }

  for (const entity of entities) {
    const inheritedChilds = subEntitiesChilds.get(entity.id);
    if (!inheritedChilds || inheritedChilds.length === 0 || !entityHasTracklets(entity)) {
      continue;
    }
    entity.ui.childs = [...(entity.ui.childs ?? []), ...inheritedChilds];
  }

  return entities;
}

function chooseLegacyTracklet(candidates: Tracklet[]): Tracklet | null {
  if (candidates.length === 0) return null;
  const ordered = candidates.slice().sort((left, right) => {
    const leftSpan = left.data.end_frame - left.data.start_frame;
    const rightSpan = right.data.end_frame - right.data.start_frame;
    if (leftSpan !== rightSpan) return leftSpan - rightSpan;
    if (left.data.start_frame !== right.data.start_frame) {
      return left.data.start_frame - right.data.start_frame;
    }
    return left.id.localeCompare(right.id);
  });
  return ordered[0] ?? null;
}

function rebuildVideoTrackletChildren(annotations: Annotation[], entities: Entity[]): Annotation[] {
  const tracklets = annotations.filter((annotation) =>
    annotation.is_type(BaseSchema.Tracklet),
  ) as Tracklet[];
  if (tracklets.length === 0) {
    return annotations;
  }

  const tracksById = new Map(tracklets.map((tracklet) => [tracklet.id, tracklet]));
  const assignments = new Map<string, Annotation[]>();

  for (const annotation of annotations) {
    if (annotation.is_type(BaseSchema.Tracklet) || annotation.ui.frame_index !== undefined) {
      annotation.ui.top_entities = [];
      tryGetTopEntityFromList(annotation, entities);
    }
  }

  for (const annotation of annotations) {
    if (annotation.is_type(BaseSchema.Tracklet)) {
      continue;
    }
    if (annotation.ui.frame_index === undefined) {
      continue;
    }

    const explicitTrackId = annotation.data.tracklet_id;
    if (typeof explicitTrackId === "string" && explicitTrackId !== "") {
      const tracklet = tracksById.get(explicitTrackId);
      if (tracklet) {
        const bucket = assignments.get(tracklet.id) ?? [];
        bucket.push(annotation);
        assignments.set(tracklet.id, bucket);
        continue;
      }
    }

    const topEntityId = annotation.ui.top_entities?.[0]?.id;
    const frameIndex = annotation.ui.frame_index;
    const viewName = annotation.data.view_name;
    if (!topEntityId || typeof viewName !== "string" || viewName === "") {
      continue;
    }

    const fallbackTrack = chooseLegacyTracklet(
      tracklets.filter((tracklet) => {
        const trackTopEntityId = tracklet.ui.top_entities?.[0]?.id;
        return (
          trackTopEntityId === topEntityId &&
          tracklet.data.view_name === viewName &&
          tracklet.data.start_frame <= frameIndex &&
          tracklet.data.end_frame >= frameIndex
        );
      }),
    );
    if (!fallbackTrack) {
      continue;
    }

    annotation.data.tracklet_id = fallbackTrack.id;
    const bucket = assignments.get(fallbackTrack.id) ?? [];
    bucket.push(annotation);
    assignments.set(fallbackTrack.id, bucket);
  }

  for (const tracklet of tracklets) {
    tracklet.ui.childs = (assignments.get(tracklet.id) ?? []).slice().sort(sortByFrameIndex);
  }

  return annotations;
}

export function normalizeWorkspaceRuntimeState(
  snapshot: WorkspaceRuntimeSnapshot,
  workspaceType: WorkspaceType,
  views: MView,
): WorkspaceRuntimeSnapshot {
  const annotations = snapshot.annotations.slice();
  annotations.forEach((annotation) =>
    ensureAnnotationRuntimeFields(annotation, workspaceType, views),
  );
  annotations.sort(sortByFrameIndex);

  const entities = rebuildEntityChildren(snapshot.entities.slice(), annotations);
  if (workspaceType === WorkspaceType.VIDEO) {
    rebuildVideoTrackletChildren(annotations, entities);
  }

  return {
    annotations,
    entities,
  };
}
