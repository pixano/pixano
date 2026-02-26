/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

import {
  Annotation,
  BaseSchema,
  Entity,
  Item,
  Tracklet,
  type DisplayControl,
} from "$lib/types/dataset";
import type { ReactiveValue } from "$lib/stores/reactiveStore.svelte";
import { toggleAnnotationDisplayControl } from "$lib/utils/displayControl";
import { getTopEntity } from "$lib/utils/entityLookupUtils";
import { saveTo } from "$lib/utils/saveItemUtils";

/**
 * Update the display control of an entity, optionally closing other entities' cards.
 */
export function setEntityDisplayControl(
  entityId: string,
  currentDisplayControl: DisplayControl,
  updates: Partial<DisplayControl>,
  entitiesStore: ReactiveValue<Entity[]>,
): void {
  const changedKeys = Object.entries(updates).filter(([key, value]) => {
    const currentValue = currentDisplayControl[key as keyof DisplayControl];
    return currentValue !== value;
  });
  if (changedKeys.length === 0) return;

  const shouldCloseOthers = updates.open === true;

  entitiesStore.update((currentEntities) => {
    let hasChanged = false;
    const nextEntities = currentEntities.map((candidate) => {
      if (candidate.id === entityId) {
        hasChanged = true;
        candidate.ui.displayControl = {
          ...candidate.ui.displayControl,
          ...updates,
        } as DisplayControl;
      } else if (shouldCloseOthers && candidate.ui.displayControl.open) {
        hasChanged = true;
        candidate.ui.displayControl = {
          ...candidate.ui.displayControl,
          open: false,
        };
      }
      return candidate;
    });
    return hasChanged ? nextEntities : currentEntities;
  });
}

/**
 * Ensure an entity's card is open (no-op if already open).
 */
export function ensureEntityCardOpen(
  entityId: string,
  currentDisplayControl: DisplayControl,
  entitiesStore: ReactiveValue<Entity[]>,
): void {
  if (currentDisplayControl.open ?? false) return;

  entitiesStore.update((currentEntities) => {
    let hasChanged = false;
    const nextEntities = currentEntities.map((candidate) => {
      if (candidate.id !== entityId || candidate.ui.displayControl.open) {
        return candidate;
      }
      hasChanged = true;
      candidate.ui.displayControl = {
        ...candidate.ui.displayControl,
        open: true,
      };
      return candidate;
    });
    return hasChanged ? nextEntities : currentEntities;
  });
}

/**
 * Toggle a display control property on annotations belonging to an entity.
 * If `child` is provided, only that child (and its tracklet children) are updated.
 * If `child` is null, all annotations under the entity are updated.
 * If `other_anns_value` is provided, all other annotations get that value.
 */
export function handleSetDisplayControl(
  entityId: string,
  currentDisplayControl: DisplayControl,
  displayControlProperty: keyof DisplayControl,
  new_value: boolean,
  child: Annotation | null,
  other_anns_value: boolean | null,
  entitiesStore: ReactiveValue<Entity[]>,
  annotationsStore: ReactiveValue<Annotation[]>,
): void {
  if (!child && displayControlProperty === "editing") {
    setEntityDisplayControl(entityId, currentDisplayControl, { editing: new_value }, entitiesStore);
  } else {
    let track_childs_ids = new Set<string>();
    if (child && child.is_type(BaseSchema.Tracklet)) {
      track_childs_ids = new Set((child as Tracklet).ui.childs.map((ann) => ann.id));
    }
    annotationsStore.update((anns) => {
      let hasChanged = false;
      const nextAnnotations = anns.map((ann) => {
        const shouldUpdate =
          (child && ann.id === child.id) ||
          track_childs_ids.has(ann.id) ||
          (!child && getTopEntity(ann).id === entityId);
        if (shouldUpdate) {
          const updated = toggleAnnotationDisplayControl(ann, displayControlProperty, new_value);
          if (updated !== ann) hasChanged = true;
          return updated;
        } else if (other_anns_value !== null) {
          const updated = toggleAnnotationDisplayControl(
            ann,
            displayControlProperty,
            other_anns_value,
          );
          if (updated !== ann) hasChanged = true;
          return updated;
        }
        return ann;
      });
      return hasChanged ? nextAnnotations : anns;
    });
  }
}

/**
 * Save a feature input change to entities or annotations.
 */
export function saveInputChange(
  value: string | boolean | number,
  propertyName: string,
  obj: Item | Entity | Annotation,
  entitiesStore: ReactiveValue<Entity[]>,
  annotationsStore: ReactiveValue<Annotation[]>,
): void {
  if (
    [BaseSchema.Track, BaseSchema.Entity, BaseSchema.MultiModalEntity].includes(
      obj.table_info.base_schema,
    )
  ) {
    entitiesStore.update((oldObjects) =>
      oldObjects.map((object) => {
        if (object === obj) {
          object.data = {
            ...object.data,
            [propertyName]: value,
          };
          saveTo("update", object);
        }
        return object;
      }),
    );
    // For canvas to reflect a name change, we need to refresh annotations store too
    annotationsStore.update((anns) => anns);
  } else if (obj.table_info.base_schema === BaseSchema.Item) {
    console.warn("This should never happen, we don't have 'item' features in Objects Inspector.");
  } else {
    // Annotation
    annotationsStore.update((oldObjects) =>
      oldObjects.map((object) => {
        if (object === obj) {
          object.data = {
            ...object.data,
            [propertyName]: value,
          };
          saveTo("update", object);
        }
        return object;
      }),
    );
  }
}
