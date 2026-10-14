<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { Check, Copy, Pencil } from "phosphor-svelte";

  import RecordStatusControl from "../../layout/RecordStatusControl.svelte";
  import UpdateFeatureInputs from "../Features/UpdateFeatureInputs.svelte";
  import { currentDatasetStore } from "$lib/stores/appStores.svelte";
  import { currentFrameIndex } from "$lib/stores/videoStores.svelte";
  import { itemMetas, mediaViews } from "$lib/stores/workspaceStores.svelte";
  import type { ItemsMeta } from "$lib/types/workspace";
  import { IconButton, Image, SequenceFrame, View } from "$lib/ui";
  import { createFeature } from "$lib/utils/featureMapping";
  import { saveTo } from "$lib/utils/saveItemUtils";
  import { getWorkspaceContext } from "$lib/workspace/context";

  // The Record tab: everything record-level — status, attributes, view metadata.
  // Display adjustments are canvas tools and live in the toolbar (DisplaySettings).
  let isEditing: boolean = $state(false);
  let copied: boolean = $state(false);
  const { manifest } = getWorkspaceContext();

  const viewData = $derived.by(() => {
    const views = Object.values(mediaViews.value || {});
    const nextViewMeta = views.map((view: View | View[]) => {
      let image: Image | SequenceFrame | undefined;
      if (Array.isArray(view)) {
        image = view[currentFrameIndex.value] as SequenceFrame | undefined;
      } else {
        image = view as Image;
      }
      return image
        ? {
            url: image.data.url,
            width: image.data.width,
            height: image.data.height,
            format: image.data.format,
            id: image.id,
            view: image.table_info.name,
          }
        : {
            url: undefined,
            width: 0,
            height: 0,
            format: "",
            id: "",
            view: "",
          };
    });
    return { viewMeta: nextViewMeta };
  });

  const features = $derived.by(() => {
    const metas = itemMetas.value;
    if (!metas?.item) return [];
    if (!manifest.tablesByName[metas.item.table_info.name]) return [];
    return createFeature(metas.item, manifest);
  });

  const datasetId = $derived(currentDatasetStore.value?.id ?? "");
  const recordId = $derived(itemMetas.value?.item?.id ?? "");

  const handleEditIconClick = (): void => {
    isEditing = !isEditing;
  };

  const handleCopyId = async (): Promise<void> => {
    if (!recordId) return;
    try {
      await navigator.clipboard.writeText(recordId);
      copied = true;
      setTimeout(() => (copied = false), 1500);
    } catch {
      // Clipboard API unavailable; leave copied state untouched.
    }
  };

  const handleTextInputChange = (
    value: string | boolean | number | Array<string | number | boolean>,
    propertyName: string,
  ) => {
    itemMetas.update((oldMetas) => {
      if (!oldMetas) return oldMetas;
      const newMetas: ItemsMeta = { ...oldMetas };
      newMetas.item.data[propertyName] = value;
      saveTo("update", newMetas.item);
      return newMetas;
    });
  };
</script>

<div class="flex flex-col gap-6 p-4 text-foreground">
  <!-- Record ID -->
  {#if recordId}
    <section class="flex flex-col gap-2">
      <div class="flex items-center justify-between">
        <h3 class="text-label text-left">ID</h3>
        <IconButton
          onclick={handleCopyId}
          tooltipContent={copied ? "Copied!" : "Copy record ID"}
          class="h-8 w-8 rounded-lg"
        >
          {#if copied}
            <Check class="h-4 w-4" />
          {:else}
            <Copy class="h-4 w-4" />
          {/if}
        </IconButton>
      </div>
      <span
        class="truncate rounded-xl border border-border/60 bg-background p-3 font-mono text-sm text-foreground"
        title={recordId}
      >
        {recordId}
      </span>
    </section>
  {/if}

  <!-- Status -->
  {#if datasetId && recordId}
    <section class="flex flex-col gap-2">
      <h3 class="text-label text-left">Status</h3>
      <RecordStatusControl {datasetId} {recordId} />
    </section>
  {/if}

  <!-- Record attributes -->
  <section class="flex flex-col gap-2">
    <div class="flex items-center justify-between">
      <h3 class="text-label text-left">Attributes</h3>
      <IconButton
        selected={isEditing}
        onclick={handleEditIconClick}
        tooltipContent="Edit record attributes"
        class="h-8 w-8 rounded-lg"
      >
        <Pencil class="h-4 w-4" />
      </IconButton>
    </div>
    {#if features.length > 0}
      <UpdateFeatureInputs
        featureClass="main"
        {features}
        {isEditing}
        saveInputChange={handleTextInputChange}
      />
    {:else}
      <p class="text-left text-sm text-muted-foreground">This record has no custom attributes.</p>
    {/if}
  </section>

  <!-- Views metadata -->
  <section class="flex flex-col gap-2">
    <h3 class="text-label text-left">Views</h3>
    {#each viewData.viewMeta as meta (meta.id)}
      <div class="rounded-xl border border-border/60 bg-background p-3">
        <p class="truncate text-left text-sm font-medium" title="{meta.id} ({meta.view})">
          {meta.view}
          <span class="font-mono text-xs text-muted-foreground">{meta.id}</span>
        </p>
        <dl class="mt-2 grid grid-cols-[90px_minmax(0,1fr)] gap-x-3 gap-y-1 text-left text-sm">
          <dt class="text-muted-foreground">URL</dt>
          <dd class="truncate" title={meta.url}>{meta.url}</dd>
          <dt class="text-muted-foreground">Size</dt>
          <dd class="tabular-nums">{meta.width} × {meta.height}</dd>
          <dt class="text-muted-foreground">Format</dt>
          <dd>{meta.format}</dd>
        </dl>
      </div>
    {/each}
  </section>
</div>
