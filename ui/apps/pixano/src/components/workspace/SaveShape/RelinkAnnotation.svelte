<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { Select } from "bits-ui";
  import { CaretDown, Check, Plus } from "phosphor-svelte";

  import { currentFrameIndex } from "$lib/stores/videoStores.svelte";
  import { colorScale, entities } from "$lib/stores/workspaceStores.svelte";
  import { Annotation, BaseSchema, type Reference } from "$lib/ui";
  import { getTopEntity } from "$lib/utils/entityLookupUtils";
  import { OVERLAPIDS_SEPARATOR } from "$lib/utils/entityRelink";
  import { buildRelinkOptions, type RelinkOption } from "$lib/utils/relinkOptions";

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

  const options = $derived(
    buildRelinkOptions({
      entities: entities.value,
      baseSchema,
      viewRef,
      track,
      trackTopEntityId: track ? getTopEntity(track).id : null,
      currentFrameIndex: currentFrameIndex.value,
    }),
  );
  const existing = $derived(options.filter((option) => option.kind !== "new"));
  const selected = $derived(options.find((option) => option.id === selectedEntityId));

  $effect(() => {
    if (options.length > 0 && !options.some((option) => option.id === selectedEntityId)) {
      selectedEntityId = options[0].id;
    }
  });

  function applySelection(option: RelinkOption | undefined) {
    if (!option || option.kind === "forbidden") return;
    selectedEntityId = option.id;
    mustMerge = option.kind === "merge";
    overlapTargetId = option.targets.join(OVERLAPIDS_SEPARATOR);
  }

  function entityColor(id: string): string {
    return id === "new" ? "transparent" : colorScale.value[1](id);
  }

  const kindChip = (option: RelinkOption): { label: string; classes: string } | null => {
    switch (option.kind) {
      case "merge":
        return { label: "Merge", classes: "bg-warning/10 text-warning" };
      case "forbidden":
        return {
          label: `${option.conflicts} conflict${option.conflicts > 1 ? "s" : ""}`,
          classes: "bg-destructive/10 text-destructive",
        };
      default:
        return null;
    }
  };
</script>

<div class="flex flex-col gap-1.5">
  <span class="text-label text-left" id="relink-label">Parent entity</span>
  <Select.Root
    type="single"
    value={selectedEntityId}
    onValueChange={(next) => applySelection(options.find((option) => option.id === next))}
  >
    <Select.Trigger
      aria-labelledby="relink-label"
      class="inline-flex h-10 w-full items-center justify-between gap-2 rounded-xl border border-input bg-background px-3 text-sm shadow-sm transition-colors hover:bg-accent/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
    >
      {#snippet children()}
        <span class="flex min-w-0 items-center gap-2">
          {#if selected?.kind === "new" || !selected}
            <Plus size={13} class="shrink-0 text-primary" />
            <span class="truncate">Create new entity</span>
          {:else}
            <span
              class="h-2.5 w-2.5 shrink-0 rounded-full"
              style:background={entityColor(selected.id)}
            ></span>
            <span class="truncate">{selected.name}</span>
          {/if}
        </span>
        <CaretDown size={13} class="shrink-0 text-muted-foreground" />
      {/snippet}
    </Select.Trigger>
    <Select.Portal>
      <Select.Content
        sideOffset={6}
        class="z-50 max-h-72 overflow-y-auto rounded-2xl border border-border/50 bg-popover/95 p-1.5 text-popover-foreground shadow-elevation-2 backdrop-blur-md"
      >
        <Select.Item
          value="new"
          label="Create new entity"
          class="flex cursor-pointer items-center gap-2 rounded-lg px-2.5 py-2 text-sm outline-none transition-colors data-[highlighted]:bg-accent data-[highlighted]:text-accent-foreground"
        >
          {#snippet children()}
            <Plus size={13} class="shrink-0 text-primary" />
            <span class="flex-1 truncate text-left">Create new entity</span>
            {#if selectedEntityId === "new"}<Check size={13} class="shrink-0 text-primary" />{/if}
          {/snippet}
        </Select.Item>
        {#if existing.length > 0}
          <Select.Group>
            <Select.GroupHeading class="text-label px-2.5 pb-1 pt-2 text-left">
              Link to existing entity
            </Select.GroupHeading>
            {#each existing as option (option.id)}
              {@const chip = kindChip(option)}
              <Select.Item
                value={option.id}
                label={option.name}
                disabled={option.kind === "forbidden"}
                class="flex cursor-pointer items-center gap-2 rounded-lg px-2.5 py-2 text-sm outline-none transition-colors data-[highlighted]:bg-accent data-[highlighted]:text-accent-foreground data-[disabled]:cursor-not-allowed data-[disabled]:opacity-50"
              >
                {#snippet children()}
                  <span
                    class="h-2.5 w-2.5 shrink-0 rounded-full"
                    style:background={entityColor(option.id)}
                  ></span>
                  <span class="min-w-0 flex-1 truncate text-left">
                    {option.name}
                    <span class="font-mono text-[10px] text-muted-foreground">{option.id}</span>
                  </span>
                  {#if chip}
                    <span
                      class="shrink-0 rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider {chip.classes}"
                      title={option.kind === "forbidden"
                        ? "An annotation of this kind already exists here for this entity"
                        : "Merges into this entity's overlapping track"}
                    >
                      {chip.label}
                    </span>
                  {/if}
                  {#if selectedEntityId === option.id}
                    <Check size={13} class="shrink-0 text-primary" />
                  {/if}
                {/snippet}
              </Select.Item>
            {/each}
          </Select.Group>
        {/if}
      </Select.Content>
    </Select.Portal>
  </Select.Root>
</div>
