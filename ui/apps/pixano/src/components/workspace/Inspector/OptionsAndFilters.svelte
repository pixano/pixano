<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports

  import { CircleSlash2 } from "lucide-svelte";

  import { Checkbox, Slider } from "bits-ui";
  import { Check } from "lucide-svelte";

  import {
    Annotation,
    BaseSchema,
    BBox,
    Entity,
    IconButton,
    Keypoints,
    Mask,
    TextSpan,
    Track,
  } from "$lib/ui";

  import { datasetSchema } from "$lib/stores/appStores.svelte";
  import { getTopEntity } from "$lib/utils/entityLookupUtils";
  import {
    annotations,
    confidenceThreshold,
    entities,
    entityFilters,
    interpolate,
  } from "$lib/stores/workspaceStores.svelte";
  import type {
    FieldCol,
    FieldOperator,
    LogicOperator,
    EntityFilter,
  } from "$lib/types/workspace";
  import FilterLine from "./FilterLine.svelte";

  interface Props {
    onFilter?: (entities: Entity[]) => void;
    onConfidenceThresholdChange?: () => void;
  }

  let { onFilter, onConfidenceThresholdChange }: Props = $props();

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
        nonFeatsFields = nonFeatsFields.concat(Track.nonFeaturesFields());
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

  const filterSetup = $derived.by(() => {
    const schema = datasetSchema.value;
    const nextTableColumns: string[] = [];
    let nextIsVideo = false;
    for (const table of schema.groups["entities"]) {
      if (schema.schemas[table].base_schema === BaseSchema.Track) nextIsVideo = true;
      if (
        entities.value.find(
          (ent) =>
            ent.table_info.name === table && ent.table_info.base_schema !== BaseSchema.Conversation,
        )
      ) {
        nextTableColumns.push(table);
      }
    }
    for (const table of schema.groups["annotations"]) {
      if (
        annotations.value.find(
          (ann) =>
            ann.table_info.name === table && ann.table_info.base_schema !== BaseSchema.Message,
        )
      ) {
        nextTableColumns.push(table);
      }
    }
    if (nextTableColumns.length === 0) {
      return {
        tableColumns: nextTableColumns,
        fieldColumns: {} as Record<string, FieldCol[]>,
        isVideo: nextIsVideo,
        disableFilter: true,
        defaultFilter: undefined as EntityFilter | undefined,
      };
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
    const firstTable = nextTableColumns[0];
    const nextFieldColumns: Record<string, FieldCol[]> = {};
    for (const table of nextTableColumns) {
      nextFieldColumns[table] = [];
      const nonFeatsFields = getNonFeaturesFields(
        schema.schemas[table].base_schema,
        tableToGroup[table],
      );
      for (const [k, v] of Object.entries(schema.schemas[table].fields)) {
        if (!v.collection && allowedTypes.includes(v.type) && !nonFeatsFields.includes(k))
          nextFieldColumns[table].push({
            name: k,
            type: v.type,
          });
      }
    }
    const nextDefaultFilter = {
      logicOperator: "FIRST",
      table: firstTable,
      name: nextFieldColumns[firstTable][0].name,
      fieldOperator: "=",
      value: "",
    } as EntityFilter;
    return {
      tableColumns: nextTableColumns,
      fieldColumns: nextFieldColumns,
      isVideo: nextIsVideo,
      disableFilter: false,
      defaultFilter: nextDefaultFilter,
    };
  });

  // Only side-effect: init entityFilters when schema changes
  let lastFilterSig = "";
  $effect(() => {
    const { tableColumns, defaultFilter } = filterSetup;
    if (!defaultFilter || tableColumns.length === 0) return;
    const sig = tableColumns.join(",");
    if (sig === lastFilterSig) return;
    lastFilterSig = sig;
    entityFilters.value = [structuredClone(defaultFilter)];
  });

  const handleAddFilter = (logicOperator: LogicOperator) => {
    if (!filterSetup.defaultFilter) return;
    const newFilter = { ...filterSetup.defaultFilter, logicOperator };
    entityFilters.value = [...entityFilters.value, newFilter]; //note: a push will not trigger reactive
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

  function groupConditions(conditions: EntityFilter[]): EntityFilter[][] {
    const groups: EntityFilter[][] = [];
    let currentGroup: EntityFilter[] = [];

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

  const filterAnnOrEnt = (annOrEnt: Annotation | Entity, cond: EntityFilter): boolean => {
    let value: string | number | boolean;
    if (cond.name === "id") value = annOrEnt.id;
    else value = annOrEnt.data[cond.name] as string | number | boolean;
    return (
      cond.table === annOrEnt.table_info.name &&
      applyOperator(value, cond.value, cond.fieldOperator)
    );
  };

  function evaluateGroups(): Entity[] {
    const groups = groupConditions(entityFilters.value);

    // Union of "OR" objets groups
    const matching = new Set<Entity>();

    for (const groupOR of groups) {
      let andRes: Entity[] = [...entities.value];
      for (const cond of groupOR) {
        let condRes: Entity[];
        if (datasetSchema.value.groups["annotations"].includes(cond.table)) {
          condRes = annotations.value
            .filter((ann) => filterAnnOrEnt(ann, cond))
            .map((ann) => getTopEntity(ann));
        }
        if (datasetSchema.value.groups["entities"].includes(cond.table)) {
          condRes = entities.value.filter((ent) => filterAnnOrEnt(ent, cond));
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
    onFilter?.(result);
  };

  const handleClearFilter = () => {
    if (filterSetup.defaultFilter) {
      entityFilters.value = [filterSetup.defaultFilter];
    }
    onFilter?.(entities.value);
  };
</script>

<div class="flex flex-col gap-2 border-2 rounded-md border-primary p-2">
  <span title="Hide all objects with confidence < threshold. O disable threshold.">
    Confidence threshold
  </span>
  <div class="flex gap-4">
    <span>0</span>
    <Slider.Root
      type="multiple"
      bind:value={confidenceThreshold.value}
      min={0}
      max={1}
      step={0.01}
      onValueChange={() => { onConfidenceThresholdChange?.(); }}
      class="relative flex w-full touch-none select-none items-center"
    >
      <span class="relative h-2 w-full grow overflow-hidden rounded-full bg-card">
        <Slider.Range class="absolute h-full bg-primary" />
      </span>
      <Slider.Thumb
        index={0}
        class="block h-5 w-5 rounded-full border-2 border-primary bg-background ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50"
      />
    </Slider.Root>
    <span>1</span>
  </div>
  {#if filterSetup.isVideo}
    <div class="flex gap-4 items-center">
      <Checkbox.Root
        checked={interpolate.value}
        onCheckedChange={(c) => { interpolate.value = c; }}
        class="peer h-4 w-4 shrink-0 rounded border border-primary ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 data-[state=checked]:bg-primary data-[state=checked]:text-primary-foreground data-[disabled]:cursor-not-allowed data-[disabled]:opacity-50"
      >
        {#snippet children({ checked })}
          <span class="flex items-center justify-center text-current h-full w-full">
            {#if checked}
              <Check class="h-3.5 w-3.5" strokeWidth={3} />
            {/if}
          </span>
        {/snippet}
      </Checkbox.Root>
      <span>Interpolate</span>
    </div>
  {/if}
  {#if !filterSetup.disableFilter}
    <div class="flex items-center justify-between w-full">
      <span class="font-medium">Filters</span>
      <div class="flex gap-4 items-center">
        <IconButton onclick={() => handleAddFilter("AND")} tooltipContent={"Add a AND condition"}>
          AND
        </IconButton>
        <IconButton onclick={() => handleAddFilter("OR")} tooltipContent={"Add a OR condition"}>
          OR
        </IconButton>
        <IconButton onclick={handleClearFilter} tooltipContent={"Clear filter"}>
          <CircleSlash2 />
        </IconButton>
      </div>
    </div>
    {#each entityFilters.value as filter}
      <FilterLine {filter} tableColumns={filterSetup.tableColumns} fieldColumns={filterSetup.fieldColumns} />
    {/each}
    <IconButton big onclick={() => handleFilterOK()} tooltipContent="Filter with conditions.">
      Filter
    </IconButton>
  {/if}
</div>
