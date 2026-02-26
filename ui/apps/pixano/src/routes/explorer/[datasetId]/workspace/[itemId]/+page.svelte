<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { persistSaveItems } from "$lib/api";
  import { PrimaryButton, effectProbe, type SaveItem } from "$lib/ui";
  import { canSave } from "$lib/stores/workspaceStores.svelte";
  import WorkspaceShell from "../../../../../components/workspace/WorkspaceShell.svelte";
  import { resolveWorkspaceVariant } from "../../../../../components/workspace/workspaceRegistry";

  import { saveCurrentItemStore } from "$lib/stores/appStores.svelte";
  import { goto } from "$app/navigation";
  import { navigating } from "$app/state";
  import { getExplorerRoute } from "$lib/utils/routes";
  import type { PageProps } from "./$types";

  let { data }: PageProps = $props();

  const isLoading = $derived(navigating.from !== null);
  const shouldSaveCurrentItem = $derived(saveCurrentItemStore.value.shouldSave);
  const Variant = $derived(resolveWorkspaceVariant(data.item?.ui?.type));

  $effect(() => {
    const value = canSave.value;
    const current = saveCurrentItemStore.value;
    if (current.canSave === value) return;
    saveCurrentItemStore.value = { ...current, canSave: value };
  });

  async function handleSaveItem(saveData: SaveItem[]) {
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

{#if data.item && data.dataset}
  <WorkspaceShell
    selectedItem={data.item}
    featureValues={data.featureValues}
    {handleSaveItem}
    {isLoading}
    {shouldSaveCurrentItem}
  >
    {#snippet viewer({ resize })}
      <Variant selectedItem={data.item} {resize} />
    {/snippet}
  </WorkspaceShell>
{/if}
{#if !data.item}
  <div class="w-full pt-40 text-center flex flex-col gap-5 items-center">
    <p>Current item could not be loaded</p>
    <PrimaryButton onclick={() => goto(getExplorerRoute(data.dataset.id))}>
      Back to dataset
    </PrimaryButton>
  </div>
{/if}
