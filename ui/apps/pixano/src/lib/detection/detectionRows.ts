/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

/** The rows that persist detection proposals (see `detection`): one object and one box each. */

import type { DetectionImage, DetectionProposal } from "./detection";
import { buildModelSourceFields } from "$lib/segmentation/maskNormalization";
import { WorkspaceType, type BBox, type Entity, type ItemFeature } from "$lib/types/dataset";
import { ShapeType, type SaveRectangleShape } from "$lib/types/shapeTypes";
import { defineCreatedAnnotation, findOrCreateEntity } from "$lib/utils/entityOperations";
import type { WorkspaceManifest } from "$lib/workspace/manifest";

export interface DetectionRowsInput {
  proposals: readonly DetectionProposal[];
  itemId: string;
  image: DetectionImage;
  manifest: WorkspaceManifest;
  /** The entity field that receives the class; `null` when the dataset has none. */
  labelField: string | null;
  className: string;
  source: { modelName: string; providerName: string };
  /** How the run asked: `text`, `exemplars` or both, kept in the rows' provenance. */
  prompt: { text: boolean; exemplars: number; negatives: number };
  workspaceType?: WorkspaceType;
}

export interface DetectionRows {
  entities: Entity[];
  bboxes: BBox[];
  /** The proposal each box was made from, index for index. */
  proposals: DetectionProposal[];
}

/**
 * One entity per proposal, its class in `labelField` when the table has one, and one box with the
 * model's score as confidence and the model as provenance. A model's row reads `pending`: the
 * review mode accepts or rejects it.
 */
export function buildDetectionRows(input: DetectionRowsInput): DetectionRows {
  const entityTable = input.manifest.tablesByGroup.entities[0] ?? "entities";
  const className = input.className.trim();
  const source = buildModelSourceFields({
    modelName: input.source.modelName,
    providerName: input.source.providerName,
    metadata: {
      ...(className ? { class: className } : {}),
      prompt: {
        text: input.prompt.text,
        exemplars: input.prompt.exemplars,
        negatives: input.prompt.negatives,
      },
    },
  });
  const viewRef = { id: input.image.viewId, name: input.image.viewName };
  const features: Record<string, ItemFeature> = {};
  if (input.labelField && className) {
    features[input.labelField] = { name: input.labelField, dtype: "str", value: className };
  }

  const entities: Entity[] = [];
  const bboxes: BBox[] = [];
  const kept: DetectionProposal[] = [];
  for (const proposal of input.proposals) {
    const entity = findOrCreateEntity(
      "new",
      { itemId: input.itemId },
      { [entityTable]: features },
      input.manifest,
    );
    const [x1, y1, x2, y2] = proposal.box;
    const shape: SaveRectangleShape = {
      type: ShapeType.bbox,
      status: "saving",
      viewRef,
      itemId: input.itemId,
      imageWidth: input.image.width,
      imageHeight: input.image.height,
      attrs: { x: x1, y: y1, width: x2 - x1, height: y2 - y1 },
    };
    const bbox = defineCreatedAnnotation(entity, {}, shape, viewRef, input.manifest, false, -1, {
      source,
    }) as BBox | undefined;
    if (!bbox) continue;
    bbox.data.confidence = proposal.score;
    bbox.ui.datasetItemType = input.workspaceType ?? WorkspaceType.IMAGE;
    bbox.ui.top_entities = [entity];
    entity.ui.childs = [bbox];
    entities.push(entity);
    bboxes.push(bbox);
    kept.push(proposal);
  }
  return { entities, bboxes, proposals: kept };
}
