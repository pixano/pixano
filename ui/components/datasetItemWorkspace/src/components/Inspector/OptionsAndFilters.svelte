<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports

  import { CircleSlash2 } from "lucide-svelte";
  import { createEventDispatcher } from "svelte";

  import {
    Annotation,
    BaseSchema,
    BBox,
    Entity,
    IconButton,
    Keypoints,
    Mask,
    TextSpan,
    Tracklet,
  } from "@pixano/core";
  import { Checkbox } from "@pixano/core/src";
  import SliderWithValue from "@pixano/core/src/components/ui/slider/SliderWithValue.svelte";

  import { datasetSchema } from "../../../../../apps/pixano/src/lib/stores/datasetStores";
  import { getTopEntity } from "../../lib/api/objectsApi";
  import {
    annotations,
    confidenceThreshold,
    entities,
    entityFilters,
    interpolate,
  } from "../../lib/stores/datasetItemWorkspaceStores";
  import type {
    FieldCol,
    FieldOperator,
    LogicOperator,
    ObjectsFilter,
  } from "../../lib/types/datasetItemWorkspaceTypes";
  import FilterLine from "./FilterLine.svelte";

  const dispatch = createEventDispatcher();

  let tableColumns: string[] = [];
  let fieldColumns: Record<string, FieldCol[]> = {};

  let disableFilter = false; //when nothing to filter, disable it
  let defaultFilter: ObjectsFilter;
  const allowedTypes = ["str", "int", "float", "bool"];

  const removeFields = (listFields: string[], toRemove: string[]) => {
    for (const rf of toRemove) {
      const index = listFields.indexOf(rf);
      if (index > -1) listFields.splice(index, 1);
    }
    return listFields;
  };

  const getNonFeaturesFields = (baseSchema: BaseSchema, group: string): string[] => {
    let nonFeatsFields: string[] = [];
    if (group === "annotations") {
      if (baseSchema === BaseSchema.BBox)
        nonFeatsFields = nonFeatsFields.concat(BBox.nonFeaturesFields());
      //keep "confidence"
      nonFeatsFields = removeFields(nonFeatsFields, ["confidence"]);
      if (baseSchema === BaseSchema.Keypoints)
        nonFeatsFields = nonFeatsFields.concat(Keypoints.nonFeaturesFields());
      if (baseSchema === BaseSchema.Mask)
        nonFeatsFields = nonFeatsFields.concat(Mask.nonFeaturesFields());
      if (baseSchema === BaseSchema.Tracklet)
        nonFeatsFields = nonFeatsFields.concat(Tracklet.nonFeaturesFields());
      //keep (start/end_timestep/stamp)
      nonFeatsFields = removeFields(nonFeatsFields, [
        "start_timestep",
        "end_timestep",
        "start_timestamp",
        "end_timestamp",
      ]);
      if (baseSchema === BaseSchema.TextSpan)
        nonFeatsFields = nonFeatsFields.concat(TextSpan.nonFeaturesFields());
    } else {
      nonFeatsFields = nonFeatsFields.concat(Entity.nonFeaturesFields());
    }
    //keep "id"
    nonFeatsFields = removeFields(nonFeatsFields, ["id"]);

    return nonFeatsFields;
  };

  datasetSchema.subscribe((schema) => {
    tableColumns = [];
    for (const table of schema.groups["entities"]) {
      if (
        $entities.find(
          (ent) =>
            ent.table_info.name === table && ent.table_info.base_schema !== BaseSchema.Conversation,
        )
      ) {
        tableColumns.push(table);
      }
    }
    for (const table of schema.groups["annotations"]) {
      if (
        $annotations.find(
          (ann) =>
            ann.table_info.name === table && ann.table_info.base_schema !== BaseSchema.Message,
        )
      ) {
        tableColumns.push(table);
      }
    }
    if (tableColumns.length === 0) {
      //ther is no objects (entity or annotations), so deactivate filtering
      disableFilter = true;
      return;
    }

    const tableToGroup = Object.entries(schema.groups).reduce(
      (acc, [group, tables]) => {
        for (const table of tables) {
          acc[table] = group;
        }
        return acc;
      },
      {} as Record<string, string>,
    );
    const firstTable = tableColumns[0];
    for (const table of tableColumns) {
      fieldColumns[table] = [];
      const nonFeatsFields = getNonFeaturesFields(
        schema.schemas[table].base_schema,
        tableToGroup[table],
      );
      for (const [k, v] of Object.entries(schema.schemas[table].fields)) {
        if (!v.collection && allowedTypes.includes(v.type) && !nonFeatsFields.includes(k))
          fieldColumns[table].push({
            name: k,
            type: v.type,
          });
      }
    }
    defaultFilter = {
      logicOperator: "FIRST",
      table: firstTable,
      name: fieldColumns[firstTable][0].name,
      fieldOperator: "=",
      value: "",
    } as ObjectsFilter;
    entityFilters.set([structuredClone(defaultFilter)]);
  });

  const handleAddFilter = (logicOperator: LogicOperator) => {
    const newFilter = { ...defaultFilter, logicOperator };
    entityFilters.set([...$entityFilters, newFilter]); //note: a push will not trigger reactive
    //TODO test si avec store ca marche en pushant
  };

  function applyOperator(
    a: number | string | boolean,
    b: string | boolean,
    op: FieldOperator,
  ): boolean {
    const val =
      typeof a === "number" && typeof b === "string"
        ? parseFloat(b)
        : typeof a === "boolean"
          ? b
            ? true
            : false
          : b;
    switch (op) {
      case "=":
        return a === val;
      case "<":
        return typeof a === "number" && a < Number(val);
      case ">":
        return typeof a === "number" && a > Number(val);
      case "<=":
        return typeof a === "number" && a <= Number(val);
      case ">=":
        return typeof a === "number" && a >= Number(val);
      case "startsWith":
        return typeof a === "string" && a.startsWith(val as string);
      case "endsWith":
        return typeof a === "string" && a.endsWith(val as string);
    }
  }

  function groupConditions(conditions: ObjectsFilter[]): ObjectsFilter[][] {
    const groups: ObjectsFilter[][] = [];
    let currentGroup: ObjectsFilter[] = [];

    for (const cond of conditions) {
      if (cond.logicOperator === "FIRST" || cond.logicOperator === "OR") {
        if (currentGroup.length) groups.push(currentGroup);
        currentGroup = [cond];
      } else {
        currentGroup.push(cond);
      }
    }
    if (currentGroup.length) groups.push(currentGroup);

    return groups;
  }

  const filterAnnOrEnt = (annOrEnt: Annotation | Entity, cond: ObjectsFilter): boolean => {
    let value: string | number | boolean;
    if (cond.name === "id") value = annOrEnt.id;
    else value = annOrEnt.data[cond.name] as string | number | boolean;
    return (
      cond.table === annOrEnt.table_info.name &&
      applyOperator(value, cond.value, cond.fieldOperator)
    );
  };

  function evaluateGroups(): Entity[] {
    const groups = groupConditions($entityFilters);

    // Union des objets correspondant à chaque groupe (OR)
    const matching = new Set<Entity>();

    for (const groupOR of groups) {
      let andRes: Entity[] = [...$entities];
      for (const cond of groupOR) {
        let condRes: Entity[];
        if ($datasetSchema.groups["annotations"].includes(cond.table)) {
          condRes = $annotations
            .filter((ann) => filterAnnOrEnt(ann, cond))
            .map((ann) => getTopEntity(ann));
        }
        if ($datasetSchema.groups["entities"].includes(cond.table)) {
          condRes = $entities.filter((ent) => filterAnnOrEnt(ent, cond));
          //in case entities are not TopEntities, get the top
          condRes = condRes.map((ent) => getTopEntity(ent));
        }
        andRes = andRes.filter((ent) => condRes.includes(ent)); //AND : intersection
      }
      andRes.forEach((ent) => matching.add(ent)); //OR: union (with a Set to remove duplicates)
    }
    return Array.from(matching);
  }

  const handleFilterOK = () => {
    const result = evaluateGroups();
    dispatch("filter", result);
  };

  const handleClearFilter = () => {
    entityFilters.set([defaultFilter]);
    dispatch("filter", $entities);
  };
</script>

<div class="flex flex-col gap-2 border-2 rounded-md border-primary p-2">
  <span title="Hide all objects with confidence < threshold. O disable threshold.">
    Confidence threshold
  </span>
  <SliderWithValue
    bind:value={$confidenceThreshold}
    onChange={() => {
      dispatch("confidenceThresholdChange");
    }}
    min={0}
    max={1}
    step={0.01}
  />
  <div class="flex gap-4 items-center">
    <Checkbox
      handleClick={() => {
        $interpolate = !$interpolate;
      }}
      checked={$interpolate}
    />
    <span>Interpolate</span>
  </div>
  {#if !disableFilter}
    <div class="flex items-center justify-between w-full">
      <span class="font-medium">Filters</span>
      <div class="flex gap-4 items-center">
        <IconButton on:click={() => handleAddFilter("AND")} tooltipContent={"Add a AND condition"}>
          AND
        </IconButton>
        <IconButton on:click={() => handleAddFilter("OR")} tooltipContent={"Add a OR condition"}>
          OR
        </IconButton>
        <IconButton on:click={handleClearFilter} tooltipContent={"Clear filter"}>
          <CircleSlash2 />
        </IconButton>
      </div>
    </div>
    {#each $entityFilters as filter}
      <FilterLine {filter} {tableColumns} {fieldColumns} />
    {/each}
    <IconButton big on:click={() => handleFilterOK()} tooltipContent="Filter with conditions.">
      Filter
    </IconButton>
  {/if}
</div>
