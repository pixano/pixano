<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { Command, Popover } from "bits-ui";
  import { CaretUpDown, Check, Plus, TextT } from "phosphor-svelte";
  import { tick } from "svelte";

  import { currentFrameIndex } from "$lib/stores/videoStores.svelte";
  import { colorScale, entities, itemMetas, mediaViews } from "$lib/stores/workspaceStores.svelte";
  import {
    Annotation,
    BaseSchema,
    Entity,
    Tracklet,
    WorkspaceType,
    type AnnotationThumbnail,
    type Reference,
  } from "$lib/ui";
  import { defineAnnotationThumbnail, getTopEntity } from "$lib/utils/entityLookupUtils";
  import { OVERLAPIDS_SEPARATOR } from "$lib/utils/entityRelink";
  import { getDefaultDisplayFeat } from "$lib/utils/workspaceDefaultFeatures";

  interface Props {
    selectedEntityId?: string;
    mustMerge?: boolean;
    overlapTargetId?: string;
    baseSchema: BaseSchema;
    viewRef: Reference;
    track?: Annotation | null;
  }

  let {
    selectedEntityId = $bindable("new"),
    mustMerge = $bindable(false),
    overlapTargetId = $bindable(""),
    baseSchema,
    viewRef,
    track = null,
  }: Props = $props();

  const entityAllowInfo = (
    entity: Entity,
  ): {
    hard_forbidden: boolean;
    overlap: boolean;
    numSameKindInSameView: number;
    overlapTargetIds: string[];
  } => {
    if (
      entity.data.parent_id !== "" ||
      entity.is_conversation ||
      (track && getTopEntity(track).id === entity.id)
    )
      return {
        hard_forbidden: true,
        overlap: false,
        numSameKindInSameView: 0,
        overlapTargetIds: [],
      };
    const entityTracks = entity.ui.childs?.filter((ann) => ann.is_type(BaseSchema.Tracklet));
    const annsNotTracks = entity.ui.childs?.filter((ann) => !ann.is_type(BaseSchema.Tracklet));
    let numSameKindInSameView: number = 0;
    let overlap: boolean | undefined = undefined;
    let overlapTargetIds: string[] = [];
    if (track && track.is_type(BaseSchema.Tracklet)) {
      const trackBaseSchemaByFrameIndex = (track as Tracklet).ui.childs.reduce(
        (acc, ann) => {
          if (ann.ui.frame_index) {
            acc[ann.ui.frame_index] = ann.table_info.base_schema;
          }
          return acc;
        },
        {} as Record<number, BaseSchema>,
      );
      const sameKindInSameView_anns = annsNotTracks?.filter(
        //NOTE we "miss" interpolated shapes. So we can "insert"
        (ann) =>
          ann.ui.frame_index
            ? ann.data.view_name === viewRef.name &&
              trackBaseSchemaByFrameIndex[ann.ui.frame_index] === ann.table_info.base_schema
            : false,
      );
      numSameKindInSameView = sameKindInSameView_anns ? sameKindInSameView_anns.length : 0;

      const overlap_tracks = entityTracks?.filter(
        (ann) =>
          (ann as Tracklet).data.view_name === viewRef.name &&
          (ann as Tracklet).data.start_frame <= (track as Tracklet).data.end_frame &&
          (ann as Tracklet).data.end_frame >= (track as Tracklet).data.start_frame,
      );
      overlap = overlap_tracks ? overlap_tracks.length > 0 : false;
      if (overlap_tracks && overlap_tracks.length > 0)
        overlapTargetIds = overlap_tracks.map((ann) => ann.id);
    } else {
      const sameKindInSameView_anns = annsNotTracks?.filter(
        //NOTE we "miss" interpolated shapes. So we can "insert"
        (ann) => ann.data.frame_id === viewRef.id && baseSchema === ann.table_info.base_schema,
      );
      numSameKindInSameView = sameKindInSameView_anns ? sameKindInSameView_anns.length : 0;
      //WARNING : if we allow relinking of a tracklet child (not allowed now)
      //$curentFrameIndex will not be reliable !
      //anyway, we should find a more reliable frame index
      const overlap_tracks = entityTracks?.filter(
        (ann) =>
          (ann as Tracklet).data.view_name === viewRef.name &&
          (ann as Tracklet).data.start_frame <= currentFrameIndex.value &&
          (ann as Tracklet).data.end_frame >= currentFrameIndex.value,
      );
      overlap = overlap_tracks ? overlap_tracks.length > 0 : false;
      if (overlap_tracks && overlap_tracks.length > 0)
        overlapTargetIds = overlap_tracks.map((ann) => ann.id);
    }
    // ! overlap --> Move
    // overlap && numSameKindInSameView === 0 --> Merge -- need to keep target tracklet
    // overlap && numSameKindInSameView > 0 --> Forbidden
    return {
      hard_forbidden: false,
      overlap: overlap ?? false,
      numSameKindInSameView,
      overlapTargetIds,
    };
  };

  interface RelinkItem {
    id: string;
    entity: Entity | null;
    kind: "new" | "move" | "merge" | "forbidden";
    conflicts: number;
    targets: string[];
    displayName: string;
  }

  // Same allow-info semantics as always — only the item payload is richer so the
  // picker can show WHO each entity is instead of a prefixed uuid string.
  let entitiesCombo = $derived.by((): RelinkItem[] => {
    const currentEntities = entities.value;
    const res: RelinkItem[] = [
      { id: "new", entity: null, kind: "new", conflicts: 0, targets: [], displayName: "" },
    ];
    currentEntities.forEach((entity) => {
      //check if there is no annotation of same kind & view_id for this entity
      const { hard_forbidden, overlap, numSameKindInSameView, overlapTargetIds } =
        entityAllowInfo(entity);
      if (!hard_forbidden) {
        const displayFeat = getDefaultDisplayFeat(entity);
        res.push({
          id: entity.id,
          entity,
          kind: overlap ? (numSameKindInSameView === 0 ? "merge" : "forbidden") : "move",
          conflicts: numSameKindInSameView,
          targets: overlapTargetIds,
          displayName: displayFeat ? String(displayFeat) : "Entity",
        });
      }
    });
    return res;
  });

  const selectedItem = $derived(entitiesCombo.find((item) => item.id === selectedEntityId));

  // ── Visual identity helpers (all reused from EntityCard's proven patterns) ──

  const entityColor = (id: string): string => colorScale.value[1](id);

  const shortId = (id: string): string => (id.length > 6 ? id.slice(-6) : id);

  const COMPOSITION_LABELS: Partial<Record<BaseSchema, string>> = {
    [BaseSchema.BBox]: "box",
    [BaseSchema.Mask]: "mask",
    [BaseSchema.Keypoints]: "keypoints",
    [BaseSchema.MultiPath]: "path",
    [BaseSchema.Tracklet]: "tracklet",
    [BaseSchema.TextSpan]: "text span",
    [BaseSchema.Classification]: "classification",
    [BaseSchema.Message]: "message",
  };

  const compositionLine = (entity: Entity): string => {
    const counts: Record<string, number> = {};
    for (const ann of entity.ui.childs ?? []) {
      // On video datasets only tracklets are countable children (same rule as EntityCard).
      if (ann.ui.datasetItemType === WorkspaceType.VIDEO && !ann.is_type(BaseSchema.Tracklet)) {
        continue;
      }
      const schema = ann.table_info.base_schema;
      counts[schema] = (counts[schema] ?? 0) + 1;
    }
    return Object.entries(counts)
      .map(([schema, count]) => {
        const label = COMPOSITION_LABELS[schema as BaseSchema] ?? schema.toLowerCase();
        const plural = count > 1 ? (label.endsWith("x") ? "es" : "s") : "";
        return `${count} ${label}${plural}`;
      })
      .join(" · ");
  };

  const entityThumbnail = (entity: Entity): AnnotationThumbnail | null => {
    const currentViews = mediaViews.value;
    const currentItemMetas = itemMetas.value;
    for (const view of Object.keys(currentViews)) {
      const candidates = entity.ui.childs?.filter(
        (ann) =>
          (ann.is_type(BaseSchema.BBox) ||
            ann.is_type(BaseSchema.Mask) ||
            ann.is_type(BaseSchema.MultiPath)) &&
          ann.data.view_name === view,
      );
      if (candidates && candidates.length > 0) {
        const preferredBox =
          candidates.find((ann) => ann.is_type(BaseSchema.BBox)) ||
          candidates[Math.floor(candidates.length / 2)];
        const thumbnail = defineAnnotationThumbnail(currentItemMetas, currentViews, preferredBox);
        if (thumbnail) return thumbnail;
      }
    }
    return null;
  };

  const hasOnlyTextSpans = (entity: Entity): boolean => {
    const childs = entity.ui.childs ?? [];
    return childs.length > 0 && childs.every((ann) => ann.is_type(BaseSchema.TextSpan));
  };

  const kindChip = (item: RelinkItem): { label: string; classes: string } | null => {
    if (item.kind === "merge") return { label: "Merge", classes: "bg-warning/10 text-warning" };
    if (item.kind === "forbidden")
      return {
        label: `${item.conflicts} conflict${item.conflicts > 1 ? "s" : ""}`,
        classes: "bg-destructive/10 text-destructive",
      };
    return null;
  };

  $effect(() => {
    if (entitiesCombo.length > 0) {
      selectedEntityId = entitiesCombo[0].id;
    }
  });

  let open = $state(false);
  const triggerId = `relink-entity-${Math.random().toString(36).slice(2, 11)}`;

  // We want to refocus the trigger button when the user selects
  // an item from the list so users can continue navigating the
  // rest of the form with the keyboard.
  function closeAndFocusTrigger(triggerId: string) {
    open = false;
    tick()
      .then(() => {
        document.getElementById(triggerId)?.focus();
      })
      .catch((err) => console.error(err));
  }

  const handleSelect = (item: RelinkItem) => {
    overlapTargetId = item.targets.join(OVERLAPIDS_SEPARATOR);
    selectedEntityId = item.id;
    mustMerge = item.kind === "merge";
    closeAndFocusTrigger(triggerId);
  };
</script>

{#snippet entityIdentity(item: RelinkItem, size: number)}
  {@const color = entityColor(item.id)}
  {@const thumb = item.entity ? entityThumbnail(item.entity) : null}
  {#if thumb}
    {@const cropW = thumb.coords[2] * thumb.baseImageDimensions.width}
    {@const cropH = thumb.coords[3] * thumb.baseImageDimensions.height}
    {@const cropAspect = cropW / cropH}
    {@const innerSize = size - 4}
    {@const fitW = cropAspect >= 1 ? innerSize : innerSize * cropAspect}
    {@const fitH = cropAspect >= 1 ? innerSize / cropAspect : innerSize}
    {@const imgScale = fitW / cropW}
    {@const imgW = thumb.baseImageDimensions.width * imgScale}
    {@const imgH = thumb.baseImageDimensions.height * imgScale}
    {@const offX = -thumb.coords[0] * thumb.baseImageDimensions.width * imgScale}
    {@const offY = -thumb.coords[1] * thumb.baseImageDimensions.height * imgScale}
    <span
      class="flex shrink-0 items-center justify-center overflow-hidden rounded-md"
      style="width: {size}px; height: {size}px; border: 2px solid {color}; background: hsl(var(--muted) / 0.8);"
    >
      <span class="relative block overflow-hidden" style="width: {fitW}px; height: {fitH}px;">
        <img
          src="/{thumb.uri}"
          alt=""
          class="absolute max-w-none"
          style="width: {imgW}px; height: {imgH}px; left: {offX}px; top: {offY}px;"
        />
      </span>
    </span>
  {:else if item.entity && hasOnlyTextSpans(item.entity)}
    <span
      class="flex shrink-0 items-center justify-center rounded-md"
      style="width: {size}px; height: {size}px; border: 2px solid {color}; background: color-mix(in srgb, {color} 14%, transparent);"
    >
      <TextT size={size / 2} weight="bold" style="color: {color};" />
    </span>
  {:else}
    <span
      class="flex shrink-0 items-center justify-center"
      style="width: {size}px; height: {size}px;"
    >
      <span class="block size-3 rounded-full" style="background: {color};"></span>
    </span>
  {/if}
{/snippet}

{#if entitiesCombo.length > 0}
  <div class="flex flex-col gap-1.5">
    <span class="text-label text-left">Parent entity</span>
    <Popover.Root bind:open>
      <Popover.Trigger
        type="button"
        id={triggerId}
        class="flex h-10 w-full items-center gap-2.5 rounded-xl border border-input bg-background px-3 text-sm text-foreground shadow-sm transition-colors hover:bg-accent/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        {#if selectedItem && selectedItem.entity}
          {@render entityIdentity(selectedItem, 26)}
          <span class="min-w-0 truncate">{selectedItem.displayName}</span>
          <span class="font-mono text-xs text-muted-foreground">{shortId(selectedItem.id)}</span>
        {:else}
          <Plus size={14} class="shrink-0 text-muted-foreground" />
          <span class="text-muted-foreground">Create new entity</span>
        {/if}
        <CaretUpDown size={14} class="ml-auto shrink-0 text-muted-foreground/70" />
      </Popover.Trigger>
      <Popover.Content
        sideOffset={6}
        class="z-50 w-[var(--bits-floating-anchor-width)] rounded-2xl border border-border/50 bg-popover/95 p-1.5 text-popover-foreground shadow-elevation-2 outline-none backdrop-blur-md"
        tabindex={-1}
      >
        <Command.Root>
          {#if entitiesCombo.length > 1}
            <Command.Input
              placeholder="Search entities…"
              class="mb-1 h-9 w-full rounded-lg border border-input bg-background px-2.5 text-sm text-foreground placeholder:text-muted-foreground/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            />
          {/if}
          <Command.List class="max-h-64 overflow-y-auto">
            <Command.Item
              value="new"
              forceMount
              onSelect={() => handleSelect(entitiesCombo[0])}
              class="flex cursor-pointer items-center gap-2.5 rounded-lg px-2 py-2 text-sm outline-none transition-colors data-[selected]:bg-accent data-[selected]:text-accent-foreground"
            >
              <span
                class="flex size-9 shrink-0 items-center justify-center rounded-md border border-dashed border-border"
              >
                <Plus size={14} class="text-muted-foreground" />
              </span>
              <span class="font-medium">Create new entity</span>
              {#if selectedEntityId === "new"}
                <Check size={14} class="ml-auto shrink-0 text-primary" />
              {/if}
            </Command.Item>
            {#if entitiesCombo.length > 1}
              <Command.Separator class="my-1 h-px bg-border/60" />
            {/if}
            {#each entitiesCombo.slice(1) as item (item.id)}
              {@const chip = kindChip(item)}
              <Command.Item
                value={item.id}
                keywords={[item.displayName, shortId(item.id)]}
                disabled={item.kind === "forbidden"}
                onSelect={() => handleSelect(item)}
                class="flex cursor-pointer items-center gap-2.5 rounded-lg px-2 py-2 text-sm outline-none transition-colors data-[disabled]:cursor-not-allowed data-[selected]:bg-accent data-[disabled]:opacity-50 data-[selected]:text-accent-foreground"
              >
                {@render entityIdentity(item, 36)}
                <span class="flex min-w-0 flex-1 flex-col items-start">
                  <span class="flex w-full min-w-0 items-baseline gap-1.5">
                    <span class="min-w-0 truncate font-medium">{item.displayName}</span>
                    <span class="shrink-0 font-mono text-[10px] text-muted-foreground">
                      {shortId(item.id)}
                    </span>
                  </span>
                  {#if item.entity}
                    {@const composition = compositionLine(item.entity)}
                    {#if composition}
                      <span class="w-full truncate text-left text-xs text-muted-foreground">
                        {composition}
                      </span>
                    {/if}
                  {/if}
                </span>
                {#if chip}
                  <span
                    class="shrink-0 rounded-md px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wider {chip.classes}"
                  >
                    {chip.label}
                  </span>
                {:else if selectedEntityId === item.id}
                  <Check size={14} class="shrink-0 text-primary" />
                {/if}
              </Command.Item>
            {/each}
            <Command.Empty class="px-2 py-3 text-center text-xs text-muted-foreground">
              No matching entity
            </Command.Empty>
          </Command.List>
        </Command.Root>
      </Popover.Content>
    </Popover.Root>
  </div>
{/if}
