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
  import { saveCurrentItemStore } from "$lib/stores/appStores.svelte";
  import { canSave } from "$lib/stores/workspaceStores.svelte";
  import { effectProbe, PrimaryButton } from "$lib/ui";
  import { getExplorerRoute } from "$lib/utils/routes";

  let { data }: PageProps = $props();

  const isLoading = $derived(navigating.from !== null);
  const shouldSaveCurrentItem = $derived(saveCurrentItemStore.value.shouldSave);
  const Variant = $derived(resolveWorkspaceVariant(data.workspaceData?.ui?.type));

  $effect(() => {
    const value = canSave.value;
    const current = saveCurrentItemStore.value;
    if (current.canSave === value) return;
    saveCurrentItemStore.value = { ...current, canSave: value };
  });

  async function handleSaveItem(saveData: ResourceMutation[]) {
    await persistSaveItems(saveData, data.dataset.id);

    const current = saveCurrentItemStore.value;
    effectProbe("WorkspacePage.resetShouldSave", {
      shouldSaveBeforeReset: current.shouldSave,
      saveItemCount: saveData.length,
    });
    if (!current.shouldSave) return;
    saveCurrentItemStore.value = { ...current, shouldSave: false };
  }
</script>

{#if data.workspaceData && data.dataset}
  <WorkspaceShell
    workspaceData={data.workspaceData}
    featureValues={data.featureValues}
    workspaceManifest={data.workspaceManifest}
    {handleSaveItem}
    {isLoading}
    {shouldSaveCurrentItem}
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
