/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import { toRawAnnotation, toRawEntity, toRawRecord, toRawView } from "./adapters";
import { ApiError, buildQueryString, requestJson } from "./apiClient";
import { normalizeTableName } from "./resourceNames";
import type {
  EntityResponse,
  ImageResponse,
  PaginatedResponse,
  RecordComponentResponse,
  RecordResponse,
  SFrameResponse,
  TextResponse,
} from "./restTypes";
import {
  Annotation,
  BaseSchema,
  Entity,
  Item,
  View,
  WorkspaceType,
  type SequenceFrame,
  type ViewEmbedding,
} from "$lib/types/dataset";
import type { WorkspaceData } from "$lib/types/workspace";
import { normalizeMediaUrl } from "$lib/utils/coreUtils";

const WORKSPACE_COLLECTIONS = [
  "bboxes",
  "masks",
  "keypoints",
  "tracklets",
  "entity-dynamic-states",
  "messages",
  "text-spans",
  "embeddings",
] as const;

const NON_WORKSPACE_ANNOTATION_TABLES = new Set(["embeddings", "entity_dynamic_states"]);

function createWorkspaceData(payload: {
  item: ReturnType<typeof toRawRecord>;
  entities: Record<string, ReturnType<typeof toRawEntity>[]>;
  annotations: Record<string, ReturnType<typeof toRawAnnotation>[]>;
  views: Record<string, ReturnType<typeof toRawView> | ReturnType<typeof toRawView>[]>;
}): WorkspaceData {
  return {
    item: new Item(payload.item),
    entities: Entity.deepCreateInstanceArrayOrPlain(payload.entities),
    annotations: Annotation.deepCreateInstanceArray(payload.annotations),
    views: View.deepCreateInstanceArrayOrPlain(payload.views),
    ui: { datasetId: "", type: WorkspaceType.UNDEFINED },
  };
}

function finalizeWorkspaceData(
  workspaceData: WorkspaceData,
  datasetId: string,
  workspaceType: WorkspaceType,
): WorkspaceData {
  if (workspaceType === WorkspaceType.VIDEO) {
    for (const viewName in workspaceData.views) {
      const view = workspaceData.views[viewName];
      if (!Array.isArray(view)) {
        throw new Error("Video workspace without SequenceFrames.");
      }
      view.forEach((sframe) => {
        const sf = sframe as SequenceFrame;
        sf.data.type = WorkspaceType.VIDEO;
        sf.data.url = normalizeMediaUrl(sf.data.url);
      });
      view.sort(
        (a, b) => (a as SequenceFrame).data.frame_index - (b as SequenceFrame).data.frame_index,
      );
    }
  } else {
    for (const viewName in workspaceData.views) {
      const view = workspaceData.views[viewName];
      if (Array.isArray(view)) {
        throw new Error("Not video workspace with SequenceFrames.");
      }
      if (view.table_info.base_schema === BaseSchema.TextView) {
        view.data.type = WorkspaceType.IMAGE_TEXT_ENTITY_LINKING;
      } else {
        view.data.type = WorkspaceType.IMAGE;
        view.data.url = normalizeMediaUrl(view.data.url as string);
      }
    }
  }

  workspaceData.ui = { type: workspaceType, datasetId };
  return workspaceData;
}

async function listAllPages<T>(
  path: string,
  params: Record<string, string | number | boolean | null | undefined> = {},
): Promise<T[]> {
  const items: T[] = [];
  let offset = 0;
  const limit = 1000;

  while (true) {
    const query = buildQueryString({ ...params, limit, offset });
    try {
      const page = await requestJson<PaginatedResponse<T>>(`${path}${query}`, {}, `list${path}`);
      items.push(...page.items);
      if (items.length >= page.total || page.items.length === 0) {
        return items;
      }
      offset += page.limit;
    } catch (error) {
      if (error instanceof ApiError && (error.status === 404 || error.status === 422)) {
        return items;
      }
      throw error;
    }
  }
}

export async function loadWorkspaceRecord(
  datasetId: string,
  recordId: string,
  workspaceType: WorkspaceType,
  resources: readonly string[] = WORKSPACE_COLLECTIONS,
): Promise<{ workspaceData: WorkspaceData }> {
  const shouldLoadImages = workspaceType !== WorkspaceType.VIDEO;
  const shouldLoadTexts = workspaceType === WorkspaceType.IMAGE_TEXT_ENTITY_LINKING;
  const shouldLoadSFrames = workspaceType === WorkspaceType.VIDEO;

  const [record, images, texts, sframes, entities, ...annotationGroups] = await Promise.all([
    requestJson<RecordResponse>(`/datasets/${datasetId}/records/${recordId}`, {}, "getRecord"),
    shouldLoadImages
      ? listAllPages<ImageResponse>(`/datasets/${datasetId}/records/${recordId}/images`)
      : Promise.resolve([]),
    shouldLoadTexts
      ? listAllPages<TextResponse>(`/datasets/${datasetId}/records/${recordId}/texts`)
      : Promise.resolve([]),
    shouldLoadSFrames
      ? listAllPages<SFrameResponse>(`/datasets/${datasetId}/records/${recordId}/sframes`)
      : Promise.resolve([]),
    listAllPages<EntityResponse>(`/datasets/${datasetId}/entities`, { record_id: recordId }),
    ...resources.map((resource) =>
      listAllPages<RecordComponentResponse>(`/datasets/${datasetId}/${resource}`, {
        record_id: recordId,
      }),
    ),
  ]);

  // eslint-disable-next-line @typescript-eslint/no-unsafe-assignment
  const views = [...images, ...texts, ...sframes];

  const viewsByLogicalName: Record<string, ReturnType<typeof toRawView>[]> = {};
  const viewNamesById = new Map<string, string>();
  for (const view of views) {
    viewNamesById.set(view.id, view.logical_name ?? "");
    // eslint-disable-next-line @typescript-eslint/no-unsafe-assignment
    const logicalName = view.logical_name ?? "default";
    viewsByLogicalName[logicalName] ??= [];
    viewsByLogicalName[logicalName].push(toRawView(view));
  }

  const entitiesByTable: Record<string, ReturnType<typeof toRawEntity>[]> = {};
  for (const entity of entities) {
    const key = "entities";
    entitiesByTable[key] ??= [];
    entitiesByTable[key].push(toRawEntity(entity, key));
  }

  const annotationsByTable: Record<string, ReturnType<typeof toRawAnnotation>[]> = {};
  for (const [index, groupComponents] of annotationGroups.entries()) {
    const key = normalizeTableName(resources[index]);
    if (NON_WORKSPACE_ANNOTATION_TABLES.has(key)) {
      continue;
    }
    annotationsByTable[key] ??= [];
    for (const component of groupComponents) {
      annotationsByTable[key].push(toRawAnnotation(component, viewNamesById, key));
    }
  }

  const normalizedViews = Object.fromEntries(
    Object.entries(viewsByLogicalName).map(([logicalName, rawViews]) => {
      const orderedViews = [...rawViews].sort((left, right) => {
        const leftFrame = typeof left.data.frame_index === "number" ? left.data.frame_index : -1;
        const rightFrame = typeof right.data.frame_index === "number" ? right.data.frame_index : -1;
        return leftFrame - rightFrame;
      });
      if (workspaceType === WorkspaceType.VIDEO) {
        return [logicalName, orderedViews];
      }
      return [logicalName, orderedViews.length === 1 ? orderedViews[0] : orderedViews];
    }),
  );

  const workspaceData = finalizeWorkspaceData(
    createWorkspaceData({
      item: toRawRecord(record),
      entities: entitiesByTable,
      annotations: annotationsByTable,
      views: normalizedViews,
    }),
    datasetId,
    workspaceType,
  );

  return {
    workspaceData,
  };
}

export async function getViewEmbeddings(
  datasetId: string,
  recordId: string,
  tableName: string,
  where: string,
): Promise<ViewEmbedding[]> {
  const query = buildQueryString({
    record_id: recordId,
    where,
    limit: 1000,
    offset: 0,
  });
  const page = await requestJson<PaginatedResponse<RecordComponentResponse>>(
    `/datasets/${datasetId}/embeddings${query}`,
    {},
    "getViewEmbeddings",
  );

  return page.items.map((embedding) => {
    const { id, created_at = "", updated_at = "", record_id = "", ...data } = embedding;
    return {
      id,
      created_at,
      updated_at,
      table_info: {
        name: normalizeTableName(tableName),
        group: "embeddings",
        base_schema: BaseSchema.Feature,
      },
      data: {
        item_id: record_id,
        view_name: typeof data.view_name === "string" ? data.view_name : "",
        frame_id: typeof data.frame_id === "string" ? data.frame_id : "",
        vector: Array.isArray(data.vector) ? (data.vector as number[]) : [],
        shape: Array.isArray(data.shape) ? (data.shape as number[]) : [],
      },
    } as ViewEmbedding;
  });
}
