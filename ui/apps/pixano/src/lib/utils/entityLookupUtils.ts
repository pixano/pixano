/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import {
  Annotation,
  BaseSchema,
  Entity,
  Source,
  WorkspaceType,
  type BBox,
  type DatasetSchema,
  type Mask,
  type AnnotationThumbnail,
  type Schema,
  type Tracklet,
} from "$lib/types/dataset";

import { PRE_ANNOTATION } from "$lib/constants/workspaceConstants";
import { sourcesStore } from "$lib/stores/appStores.svelte";
import { entities } from "$lib/stores/workspaceStores.svelte";
import { saveTo } from "$lib/utils/saveItemUtils";
import { nowTimestamp } from "$lib/utils/coreUtils";
import type { ItemsMeta, MView } from "$lib/types/workspace";

/**
 * Pure variant of getTopEntity that accepts an entities list directly,
 * avoiding reading the store through the Svelte 5 proxy during loadData().
 */
export const getTopEntityFromList = (
  obj: Annotation | Entity,
  entitiesList: Entity[],
): Entity => {
  let entity: Entity | undefined;
  if (obj.table_info.group === "entities") {
    entity = obj as Entity;
    while (entity && entity.data.parent_id !== "") {
      entity = entitiesList.find(
        (parent_entity) => entity && parent_entity.id === entity.data.parent_id,
      );
    }
    if (!entity) {
      console.error("ERROR: Unable to find top level Entity of entity", obj);
      throw new Error(`ERROR: Unable to find top level Entity of entity (id=${obj.id})`);
    }
  } else {
    const ann = obj as Annotation;
    if (ann.ui.top_entities && ann.ui.top_entities.length > 0) {
      return ann.ui.top_entities[0];
    }
    ann.ui.top_entities = [];
    entity = entitiesList.find((entity) => entity.id === ann.data.entity_id);
    while (entity && entity.data.parent_id !== "") {
      ann.ui.top_entities.unshift(entity);
      entity = entitiesList.find(
        (parent_entity) => entity && parent_entity.id === entity.data.parent_id,
      );
    }
    if (!entity) {
      console.error("ERROR: Unable to find top level Entity of annotation", ann);
      throw new Error(`ERROR: Unable to find top level Entity of annotation (id=${ann.id})`);
    }
    ann.ui.top_entities.unshift(entity);
  }
  return entity;
};

export const getTopEntity = (obj: Annotation | Entity): Entity => {
  return getTopEntityFromList(obj, entities.value);
};

export const getPixanoSource = (srcStore: { value: Source[]; update(fn: (prev: Source[]) => Source[]): void }): Source => {
  //manage source: add if we need it
  //TMP (TODO) - currently, all add/update from Pixano App are under a same unique source
  const sources = srcStore.value;
  let pixanoSource = sources.find((src) => src.data.name === "Pixano" && src.data.kind === "other");
  if (!pixanoSource) {
    const now = nowTimestamp();
    pixanoSource = new Source({
      id: "pixano_source",
      created_at: now,
      updated_at: now,
      table_info: { name: "source", group: "source", base_schema: BaseSchema.Source },
      data: { name: "Pixano", kind: "other", metadata: {} },
    });
    srcStore.update((sources) => {
      sources.push(pixanoSource);
      return sources;
    });
    //save it
    saveTo("add", pixanoSource);
  }
  return pixanoSource;
};

type SourceStampedSchema = Schema & { data: { source_id: string } };

export const getPixanoSourceId = (
  srcStore: { value: Source[]; update(fn: (prev: Source[]) => Source[]): void } = sourcesStore,
): string => getPixanoSource(srcStore).id;

export const stampWithPixanoSource = <T extends { data: { source_id: string } }>(
  obj: T,
  srcStore: { value: Source[]; update(fn: (prev: Source[]) => Source[]): void } = sourcesStore,
): T => {
  obj.data.source_id = getPixanoSourceId(srcStore);
  return obj;
};

export const saveUpdatedWithPixanoSource = <T extends SourceStampedSchema>(
  obj: T,
  srcStore: { value: Source[]; update(fn: (prev: Source[]) => Source[]): void } = sourcesStore,
): T => {
  stampWithPixanoSource(obj, srcStore);
  saveTo("update", obj);
  return obj;
};

export const saveAddedWithPixanoSource = <T extends SourceStampedSchema>(
  obj: T,
  srcStore: { value: Source[]; update(fn: (prev: Source[]) => Source[]): void } = sourcesStore,
): T => {
  stampWithPixanoSource(obj, srcStore);
  saveTo("add", obj);
  return obj;
};

export const getAnnotationsToPreAnnotate = (objects: Annotation[]): Annotation[] => {
  const sources = sourcesStore.value;
  return objects.filter((object) => {
    const source = sources.find((s) => s.id === object.data.source_id);
    return source?.data.name === PRE_ANNOTATION && !object.ui.review_state;
  });
};

export const getTable = (
  dataset_schema: DatasetSchema,
  group: keyof DatasetSchema["groups"],
  base_schema: BaseSchema,
): string => {
  for (const group_table of dataset_schema.groups[group]) {
    if (dataset_schema.schemas[group_table].base_schema === base_schema) {
      return group_table;
    }
  }
  return dataset_schema.groups[group][0];
};

export const sortAndFilterAnnotations = (
  objects: Annotation[],
  confidenceFilterValue: number[],
  currentFrameIndex: number,
): Annotation[] => {
  return objects
    .filter((object) => {
      if (object.ui.datasetItemType === WorkspaceType.IMAGE && object.is_type(BaseSchema.BBox)) {
        const confidence = (object as BBox).data.confidence || 0;
        return confidence >= confidenceFilterValue[0];
      }
      if (
        object.ui.datasetItemType === WorkspaceType.VIDEO &&
        object.is_type(BaseSchema.BBox) &&
        object.ui.frame_index === currentFrameIndex
      ) {
        const confidence = (object as BBox).data.confidence || 0;
        return confidence >= confidenceFilterValue[0];
      }
      return false;
    })
    .sort((a, b) => {
      const firstBoxXPosition = (a as BBox).data.coords[0] || 0;
      const secondBoxXPosition = (b as BBox).data.coords[0] || 0;
      return firstBoxXPosition - secondBoxXPosition;
    });
};

export const defineAnnotationThumbnail = (
  metas: ItemsMeta | undefined,
  views: MView,
  object: Annotation,
): AnnotationThumbnail | null => {
  let coords: number[] | undefined = undefined;
  let frame_index: number | undefined = undefined;

  if (object.is_type(BaseSchema.BBox)) {
    const box = object as BBox;
    coords = box.data.coords;
    frame_index = box.ui.frame_index;
  } else if (object.is_type(BaseSchema.Mask)) {
    const mask = object as Mask;
    if (mask.ui.bounds) {
      const b = mask.ui.bounds;
      coords = [b.x, b.y, b.width, b.height];
    }
    frame_index = mask.ui.frame_index;
  }

  const view_name = object.data.view_name;
  if (!coords || !view_name || !metas) return null;
  if (!(view_name in views)) return null;
  const candidateView = views[view_name];
  if (!candidateView) return null;

  const viewData =
    metas.type === WorkspaceType.VIDEO
      ? (() => {
          if (frame_index === undefined || !Array.isArray(candidateView)) return null;
          const frame = (candidateView)[frame_index];
          return frame?.data ?? null;
        })()
      : (() => {
          if (Array.isArray(candidateView)) return null;
          return (candidateView).data;
        })();

  if (!viewData?.url) return null;
  if (viewData.width === undefined || viewData.height === undefined) return null;

  if (object.is_type(BaseSchema.Mask) || !(object as BBox).data.is_normalized) {
    coords = [
      coords[0] / viewData.width,
      coords[1] / viewData.height,
      coords[2] / viewData.width,
      coords[3] / viewData.height,
    ];
  }
  return {
    baseImageDimensions: {
      width: viewData.width,
      height: viewData.height,
    },
    coords,
    uri: viewData.url,
    view: view_name,
  };
};

const getFirstTrackFrame = (entity: Entity): number => {
  return entity.ui.childs && entity.ui.childs.length > 0
    ? Math.min(
        ...entity.ui.childs
          .filter((ann) => ann.is_type(BaseSchema.Tracklet))
          .map((trk) => (trk as Tracklet).data.start_frame),
      )
    : Infinity;
};

export const sortEntities = (a: Entity, b: Entity): number => {
  let result = 0;
  if (a.is_type(BaseSchema.Track) && b.is_type(BaseSchema.Track)) {
    result = getFirstTrackFrame(a) - getFirstTrackFrame(b);
  }
  if (result === 0 && "name" in a.data && "name" in b.data) {
    result = (a.data["name"] as string).localeCompare(b.data["name"] as string);
  }
  if (result === 0) {
    result = a.id.localeCompare(b.id);
  }
  return result;
};
