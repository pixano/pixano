<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { resolveWorkspaceVariant } from "../../../../../components/workspace/workspaceRegistry";
  import WorkspaceShell from "../../../../../components/workspace/WorkspaceShell.svelte";
  import type { PageProps } from "./$types";
  import { goto } from "$app/navigation";
  import { navigating, page } from "$app/state";
  import { persistSaveItems } from "$lib/api";
  import { currentItemSaveCoordinator } from "$lib/stores/appStores.svelte";
  import {
    canSave,
    reviewModeIsActive,
    workspaceSaveQueue,
  } from "$lib/stores/workspaceStores.svelte";
  import { PrimaryButton } from "$lib/ui";
  import { createReviewReflection } from "$lib/utils/reviewActions";
  import { isReviewedWorkspace } from "$lib/utils/reviewStatus";
  import { getExplorerRoute, isReviewRoute } from "$lib/utils/routes";

  let { data }: PageProps = $props();

  const isLoading = $derived(navigating.from !== null);
  const Variant = $derived(resolveWorkspaceVariant(data.workspaceData?.ui?.type));

  let lastObservedItemId = $state<string | null>(null);

  $effect(() => {
    currentItemSaveCoordinator.syncDirty(canSave.value);
  });

  $effect(() => {
    const currentItemId = data.workspaceData?.item?.id
      ? `${data.dataset.id}/${data.workspaceData.item.id}`
      : null;
    if (currentItemId === lastObservedItemId) return;
    lastObservedItemId = currentItemId;
    currentItemSaveCoordinator.resetForItemChange();
  });

  // A record opened in review, from the explorer's Review or by "Save & next", turns the review
  // mode on, where this interface reviews the record's annotations. The mode then lasts from
  // record to record until it is turned off.
  $effect(() => {
    const workspace = data.workspaceData?.ui.type;
    if (isReviewRoute(page.url) && workspace && isReviewedWorkspace(workspace)) {
      reviewModeIsActive.value = true;
    }
  });

  async function handleSaveItem() {
    const reflection = createReviewReflection(data.dataset.id);
    try {
      await persistSaveItems(workspaceSaveQueue, data.dataset.id, reflection.onPersisted);
    } finally {
      await reflection.finish();
    }
  }
</script>

{#if data.workspaceData && data.dataset}
  <WorkspaceShell
    workspaceData={data.workspaceData}
    featureValues={data.featureValues}
    workspaceManifest={data.workspaceManifest}
    {handleSaveItem}
    {isLoading}
  >
    {#snippet viewer({ resize })}
      <Variant selectedItem={data.workspaceData} {resize} />
    {/snippet}
  </WorkspaceShell>
{/if}
{#if !data.workspaceData}
  <div class="w-full pt-40 text-center flex flex-col gap-5 items-center">
    <p>This record could not be loaded</p>
    <PrimaryButton onclick={() => goto(getExplorerRoute(data.dataset.id))}>
      Back to dataset
    </PrimaryButton>
  </div>
{/if}
