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
  import { navigating } from "$app/state";
  import { persistSaveItems } from "$lib/api";
  import type { ResourceMutation } from "$lib/api/resourcePayloads";
  import { currentItemSaveCoordinator } from "$lib/stores/appStores.svelte";
  import { canSave } from "$lib/stores/workspaceStores.svelte";
  import { PrimaryButton } from "$lib/ui";
  import { getExplorerRoute } from "$lib/utils/routes";

  let { data }: PageProps = $props();

  const isLoading = $derived(navigating.from !== null);
  const Variant = $derived(resolveWorkspaceVariant(data.workspaceData?.ui?.type));

  let lastObservedItemId = $state<string | null>(null);

  $effect(() => {
    currentItemSaveCoordinator.syncDirty(canSave.value);
  });

  $effect(() => {
    const currentItemId = data.workspaceData?.item?.id ?? null;
    if (currentItemId === lastObservedItemId) return;
    lastObservedItemId = currentItemId;
    currentItemSaveCoordinator.resetForItemChange();
  });

  async function handleSaveItem(saveData: ResourceMutation[]) {
    await persistSaveItems(saveData, data.dataset.id);
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
    <p>Current item could not be loaded</p>
    <PrimaryButton onclick={() => goto(getExplorerRoute(data.dataset.id))}>
      Back to dataset
    </PrimaryButton>
  </div>
{/if}
