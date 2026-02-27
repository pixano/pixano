<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports

  import { Check, Plus, Prohibit } from "phosphor-svelte";

  import { Checkbox, Slider } from "bits-ui";

  import {
    Annotation,
    BaseSchema,
    BBox,
    Entity,
    Keypoints,
    Mask,
    TextSpan,
    Tracklet,
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
        nonFeatsFields = nonFeatsFields.concat(Tracklet.nonFeaturesFields());
      //keep (start/end_frame/stamp)
      nonFeatsFields = removeFields(nonFeatsFields, [
        "start_frame",
        "end_frame",
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
    const candidateTables: string[] = [];
    let nextIsVideo = false;

    for (const table of schema.groups["entities"]) {
      if (schema.schemas[table].base_schema === BaseSchema.Track) nextIsVideo = true;
      if (
        entities.value.find(
          (ent) =>
            ent.table_info.name === table && ent.table_info.base_schema !== BaseSchema.Conversation,
        )
      ) {
        candidateTables.push(table);
      }
    }

    for (const table of schema.groups["annotations"]) {
      if (
        annotations.value.find(
          (ann) =>
            ann.table_info.name === table && ann.table_info.base_schema !== BaseSchema.Message,
        )
      ) {
        candidateTables.push(table);
      }
    }

    if (candidateTables.length === 0) {
      return {
        tableColumns: [] as string[],
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

    const nextFieldColumns: Record<string, FieldCol[]> = {};
    for (const table of candidateTables) {
      nextFieldColumns[table] = [];
      const nonFeatsFields = getNonFeaturesFields(
        schema.schemas[table].base_schema,
        tableToGroup[table],
      );
      for (const [k, v] of Object.entries(schema.schemas[table].fields)) {
        if (!v.collection && allowedTypes.includes(v.type) && !nonFeatsFields.includes(k)) {
          nextFieldColumns[table].push({ name: k, type: v.type });
        }
      }
    }

    const filterableTables = candidateTables.filter(
      (table) => (nextFieldColumns[table] ?? []).length > 0,
    );

    if (filterableTables.length === 0) {
      return {
        tableColumns: [] as string[],
        fieldColumns: nextFieldColumns,
        isVideo: nextIsVideo,
        disableFilter: true,
        defaultFilter: undefined as EntityFilter | undefined,
      };
    }

    const firstTable = filterableTables[0];
    const firstField = nextFieldColumns[firstTable][0];

    const nextDefaultFilter = {
      logicOperator: "FIRST",
      table: firstTable,
      name: firstField.name,
      fieldOperator: "=",
      value: "",
    } as EntityFilter;

    return {
      tableColumns: filterableTables,
      fieldColumns: nextFieldColumns,
      isVideo: nextIsVideo,
      disableFilter: false,
      defaultFilter: nextDefaultFilter,
    };
  });

  const confidenceValueLabel = $derived.by(() => (confidenceThreshold.value[0] ?? 0).toFixed(2));

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
    const newFilter = { ...structuredClone(filterSetup.defaultFilter), logicOperator };
    entityFilters.value = [...entityFilters.value, newFilter]; //note: a push will not trigger reactive
  };

  function applyOperator(
    a: number | string | boolean,
    b: string | boolean,
    op: FieldOperator,
  ): boolean {
    const val =
      typeof a === "number"
        ? Number(b)
        : typeof a === "boolean"
          ? (typeof b === "boolean" ? b : b === "true")
          : String(b);

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
    const rawValue = cond.name === "id" ? annOrEnt.id : annOrEnt.data[cond.name];
    if (rawValue === undefined || rawValue === null) return false;
    const value = rawValue as string | number | boolean;

    return (
      cond.table === annOrEnt.table_info.name &&
      applyOperator(value, cond.value, cond.fieldOperator)
    );
  };

  function evaluateGroups(): Entity[] {
    const groups = groupConditions(entityFilters.value);
    if (groups.length === 0) return [...entities.value];

    // Union of "OR" objets groups
    const matching = new Set<Entity>();

    for (const groupOR of groups) {
      let andRes: Entity[] = [...entities.value];
      for (const cond of groupOR) {
        let condRes: Entity[] = [];
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
      entityFilters.value = [structuredClone(filterSetup.defaultFilter)];
    }
    onFilter?.(entities.value);
  };
</script>

<div class="flex flex-col gap-3 rounded-xl border border-border/50 bg-muted/20 p-3">
  <div class="space-y-2">
    <div class="flex items-center justify-between">
      <span
        class="text-[11px] font-semibold uppercase tracking-[0.05em] text-muted-foreground"
        title="Hide all objects with confidence below threshold. 0 disables threshold."
      >
        Confidence threshold
      </span>
      <span class="text-xs tabular-nums text-muted-foreground">{confidenceValueLabel}</span>
    </div>

    <div class="flex items-center gap-2">
      <span class="text-[10px] text-muted-foreground">0</span>
      <Slider.Root
        type="multiple"
        bind:value={confidenceThreshold.value}
        min={0}
        max={1}
        step={0.01}
        onValueChange={() => {
          onConfidenceThresholdChange?.();
        }}
        class="relative flex w-full touch-none select-none items-center"
      >
        <span class="relative h-2 w-full grow overflow-hidden rounded-full bg-background">
          <Slider.Range class="absolute h-full bg-primary" />
        </span>
        <Slider.Thumb
          index={0}
          class="block h-4 w-4 rounded-full border-2 border-primary bg-background ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
        />
      </Slider.Root>
      <span class="text-[10px] text-muted-foreground">1</span>
    </div>
  </div>

  {#if filterSetup.isVideo}
    <div class="flex items-center gap-2 rounded-lg border border-border/40 bg-background/60 px-2 py-1.5">
      <Checkbox.Root
        checked={interpolate.value}
        onCheckedChange={(c) => {
          interpolate.value = c;
        }}
        class="peer h-4 w-4 shrink-0 rounded border border-primary ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 data-[state=checked]:bg-primary data-[state=checked]:text-primary-foreground"
      >
        {#snippet children({ checked })}
          <span class="flex items-center justify-center text-current h-full w-full">
            {#if checked}
              <Check class="h-3.5 w-3.5" />
            {/if}
          </span>
        {/snippet}
      </Checkbox.Root>
      <span class="text-xs text-muted-foreground">Interpolate track visibility</span>
    </div>
  {/if}

  {#if !filterSetup.disableFilter}
    <div class="space-y-2 border-t border-border/40 pt-3">
      <div class="flex items-center justify-between gap-2">
        <span class="text-[11px] font-semibold uppercase tracking-[0.05em] text-muted-foreground">
          Advanced Rules
        </span>

        <div class="flex items-center gap-1.5">
          <button
            type="button"
            onclick={() => handleAddFilter("AND")}
            class="h-7 inline-flex items-center gap-1 rounded-md border border-border/50 bg-background px-2 text-[10px] font-semibold tracking-wide text-foreground hover:bg-accent transition-colors"
            title="Add an AND condition"
          >
            <Plus class="h-3 w-3" />
            AND
          </button>
          <button
            type="button"
            onclick={() => handleAddFilter("OR")}
            class="h-7 inline-flex items-center gap-1 rounded-md border border-border/50 bg-background px-2 text-[10px] font-semibold tracking-wide text-foreground hover:bg-accent transition-colors"
            title="Add an OR condition"
          >
            <Plus class="h-3 w-3" />
            OR
          </button>
        </div>
      </div>

      <div class="space-y-2">
        {#each entityFilters.value as filter}
          <FilterLine
            {filter}
            tableColumns={filterSetup.tableColumns}
            fieldColumns={filterSetup.fieldColumns}
          />
        {/each}
      </div>

      <div class="flex items-center justify-end gap-2 pt-1">
        <button
          type="button"
          onclick={handleClearFilter}
          class="h-8 inline-flex items-center gap-1 rounded-lg border border-border/60 bg-background px-2.5 text-xs font-medium text-muted-foreground hover:text-foreground hover:bg-accent transition-colors"
          title="Clear all filter rules"
        >
          <Prohibit class="h-3.5 w-3.5" />
          Clear
        </button>

        <button
          type="button"
          onclick={handleFilterOK}
          class="h-8 rounded-lg bg-primary px-3 text-xs font-semibold text-primary-foreground hover:bg-primary/90 transition-colors"
          title="Apply current filter rules"
        >
          Apply filters
        </button>
      </div>
    </div>
  {:else}
    <div class="rounded-lg border border-border/40 bg-background/60 px-2.5 py-2 text-xs text-muted-foreground">
      No filterable fields are available for this item.
    </div>
  {/if}
</div>
