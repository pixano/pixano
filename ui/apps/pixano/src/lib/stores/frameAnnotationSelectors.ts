/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { Annotation, BBox, Entity, Keypoints, SequenceFrame, Tracklet } from "$lib/types/dataset";
import { ToolType } from "$lib/types/tools";
import type { MView } from "$lib/types/workspace";
import { getEffectiveHighlight, type HighlightState } from "$lib/utils/highlightUtils";

export function getAnnotationFrameIndex(annotation: Annotation): number | undefined {
  if (typeof annotation.ui.frame_index === "number") {
    return annotation.ui.frame_index;
  }

  const dataFrameIndex = annotation.data.frame_index;
  return typeof dataFrameIndex === "number" ? dataFrameIndex : undefined;
}

export function getBBoxInterpolationIdentity(bbox: BBox): string {
  return `${bbox.data.entity_id}|${bbox.data.view_name}`;
}

export function getKeypointsInterpolationIdentity(keypoints: Keypoints): string {
  return `${keypoints.data.entity_id}|${keypoints.data.view_name}|${keypoints.data.template_id}`;
}

export function collectExactFrameAnnotations<TRaw extends Annotation, TDisplay>(opts: {
  frameAnnotations: TRaw[];
  mapForDisplay: (ann: TRaw, highlight: HighlightState) => TDisplay | undefined;
  focusedEntityId: string | null;
  selectedToolType: ToolType;
  entitiesById: Map<string, Entity> | null;
}): TDisplay[] {
  return opts.frameAnnotations
    .map((ann) =>
      opts.mapForDisplay(
        ann,
        getEffectiveHighlight(ann, opts.focusedEntityId, opts.selectedToolType, opts.entitiesById),
      ),
    )
    .filter((value): value is TDisplay => value !== undefined);
}

export function collectFrameAnnotations<
  TRaw extends Annotation,
  TDisplay extends { id: string },
>(opts: {
  frameAnnotations: TRaw[];
  typeFilter: (ann: Annotation) => ann is TRaw;
  mapForDisplay: (ann: TRaw, highlight: HighlightState) => TDisplay | undefined;
  interpolateFn: (mapped: TDisplay[], frameIdx: number, frameId: string) => TDisplay | null;
  interpolationIdentity?: (ann: TRaw) => string;
  frameIdx: number;
  doInterpolate: boolean;
  tracks: Tracklet[];
  mViews: MView;
  focusedEntityId: string | null;
  selectedToolType: ToolType;
  entitiesById: Map<string, Entity> | null;
}): { results: TDisplay[]; seenIds: Set<string> } {
  const results: TDisplay[] = [];
  const seenIds = new Set<string>();
  const exactInterpolationIdentities = new Set<string>();

  for (const ann of opts.frameAnnotations) {
    const mapped = opts.mapForDisplay(
      ann,
      getEffectiveHighlight(ann, opts.focusedEntityId, opts.selectedToolType, opts.entitiesById),
    );
    if (!mapped) continue;

    results.push(mapped);
    seenIds.add(mapped.id);
    const interpolationIdentity = opts.interpolationIdentity?.(ann);
    if (interpolationIdentity) {
      exactInterpolationIdentities.add(interpolationIdentity);
    }
  }

  if (!opts.doInterpolate) {
    return { results, seenIds };
  }

  const currentTracklets = opts.tracks.filter(
    (tracklet) =>
      tracklet.data.start_frame <= opts.frameIdx && tracklet.data.end_frame >= opts.frameIdx,
  );

  for (const tracklet of currentTracklets) {
    const childs = (tracklet.ui.childs ?? []).filter(opts.typeFilter);
    if (childs.length === 0) continue;

    const interpolationIdentity = opts.interpolationIdentity?.(childs[0]);
    if (interpolationIdentity && exactInterpolationIdentities.has(interpolationIdentity)) {
      continue;
    }

    const atFrame = childs.find((ann) => ann.ui.frame_index === opts.frameIdx);
    if (atFrame) {
      const mapped = opts.mapForDisplay(
        atFrame,
        getEffectiveHighlight(
          atFrame,
          opts.focusedEntityId,
          opts.selectedToolType,
          opts.entitiesById,
        ),
      );
      if (mapped && !seenIds.has(mapped.id)) {
        results.push(mapped);
        seenIds.add(mapped.id);
      }
      continue;
    }

    if (childs.length <= 1) continue;

    const sample = childs[0];
    const viewFrames = opts.mViews[sample.data.view_name] as SequenceFrame[] | undefined;
    const viewFrame = viewFrames?.[opts.frameIdx];
    if (!viewFrame) continue;

    const mappedChilds = childs
      .map((ann) =>
        opts.mapForDisplay(
          ann,
          getEffectiveHighlight(
            ann,
            opts.focusedEntityId,
            opts.selectedToolType,
            opts.entitiesById,
          ),
        ),
      )
      .filter((value): value is TDisplay => value !== undefined);
    const interpolated = opts.interpolateFn(mappedChilds, opts.frameIdx, viewFrame.id);
    if (interpolated && !seenIds.has(interpolated.id)) {
      results.push(interpolated);
      seenIds.add(interpolated.id);
    }
  }

  return { results, seenIds };
}
