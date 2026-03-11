/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import * as ort from "onnxruntime-web";

import { reactiveStore, reactiveRawStore } from "./reactiveStore.svelte";
import type { ResourceMutation } from "$lib/api/resourcePayloads";
import type { InteractiveImageSegmenter } from "$lib/models";
import { panTool, type SelectionTool } from "$lib/tools";
import {
  Annotation,
  BBox,
  Entity,
  View,
} from "$lib/types/dataset";
import type { KeypointAnnotation, Shape } from "$lib/types/shapeTypes";
import type {
  EntityFilter,
  Filters,
  ItemsMeta,
  Merges,
  ModelSelection,
} from "$lib/types/workspace";

export const newShape = reactiveStore<Shape>({ status: "none" });
export const selectedTool = reactiveStore<SelectionTool>(panTool);
export const highlightedEntity = reactiveStore<string | null>(null);
export const annotations = reactiveStore<Annotation[]>([]);
export const generatedPreviewBBoxes = reactiveStore<BBox[]>([]);
export const entities = reactiveStore<Entity[]>([]);
export const views = reactiveStore<Record<string, View | View[]>>({});
export const merges = reactiveStore<Merges>({ to_fuse: [], forbids: [] });
export const interactiveSegmenterModel = reactiveRawStore<InteractiveImageSegmenter | undefined>(
  undefined,
);
export const itemMetas = reactiveStore<ItemsMeta | undefined>(undefined);
export const preAnnotationIsActive = reactiveStore<boolean>(false);
export const modelsUiStore = reactiveStore<ModelSelection>({
  currentModalOpen: "none",
  selectedModelName: "",
  selectedTableName: "",
  yetToLoadEmbedding: true,
});
export const embeddings = reactiveRawStore<Record<string, ort.Tensor>>({});
export const filters = reactiveStore<Filters>({
  brightness: 0,
  contrast: 0,
  equalizeHistogram: false,
  redRange: [0, 255],
  greenRange: [0, 255],
  blueRange: [0, 255],
  u16BitRange: [0, 65535],
});
export const imageSmoothing = reactiveStore<boolean>(true);
export const brushSettings = reactiveStore({ brushRadius: 20, lazyRadius: 10, friction: 0.15 });
export const selectedKeypointsTemplate = reactiveStore<KeypointAnnotation["template_id"] | null>(
  null,
);
export const saveData = reactiveStore<ResourceMutation[]>([]);

export const canSave = {
  get value() {
    return saveData.value.length > 0;
  },
};

export const interpolate = reactiveStore<boolean>(true);
export const confidenceThreshold = reactiveStore<number[]>([0.0]);
export const entityFilters = reactiveStore<EntityFilter[]>([]);
