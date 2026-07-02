/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import type { ViewInfo } from "$lib/annotations/seedLoaders.js";
import type { EntityRow } from "$lib/api/annotations.js";
import type { SchemaDescriptor } from "$lib/types/dataset";

import type { DatasetGateway } from "./datasetGateway.js";

/**
 * Per-extension contract for "seed a widget from a (record, view) pair".
 *
 * `RecordLoader` walks every view in a record and asks each registered
 * `WidgetExtensionConfig` (in registry priority order) whether its
 * `addRecordSeed` claims that view. The first non-null result wins.
 *
 * Each extension owns:
 *   - which `viewDef.base` values it claims,
 *   - which gateway calls it makes,
 *   - what shape its `options`, `data`, and seed `storage` take.
 *
 * The loader owns:
 *   - the layout and ordering of resulting widgets,
 *   - the parallel fan-out across views,
 *   - the entities-by-id map (built once, shared with all extensions).
 *
 * To support a new view type, write a new extension file and register it;
 * no change to the loader is required.
 */

export interface SeedContext {
  datasetId: string;
  recordId: string;
  viewName: string;
  viewDef: SchemaDescriptor;
  /** Pre-fetched entity index for the current record, shared across views. */
  entitiesById: Map<string, EntityRow>;
  /**
   * Gateway the seed uses to fetch view-scoped data. The loader only
   * actually exercises `RecordReadGateway` methods; the wider type is
   * accepted here so a single instance can be passed through.
   */
  gateway: DatasetGateway;
}

/**
 * Returned by `addRecordSeed` when the extension claims a view. Return
 * `null` to defer to the next extension.
 *
 * `seed.storage` is merged into whatever `WidgetExtensionConfig.addStorage`
 * produces, atomically with widget creation, so the widget mounts already
 * populated.
 *
 * `seed.view` describes the claimed view (canonical row id, logical name,
 * media dimensions). The loader indexes every claimed view and hands the
 * index to the per-kind `SEED_LOADERS`, which fetch and map the record's
 * annotations once — extensions never fetch annotations themselves.
 */
export interface RecordWidgetSeed<
  TStorage extends Record<string, unknown> = Record<string, unknown>,
> {
  /** Defaults to the view's logical name. */
  title?: string;
  options?: Record<string, unknown>;
  data?: Record<string, unknown>;
  storage?: Partial<TStorage>;
  view?: ViewInfo;
}
