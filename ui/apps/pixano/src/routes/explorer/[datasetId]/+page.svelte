<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import DatasetExplorer from "../../../components/dataset/DatasetExplorer.svelte";
  import type { PageProps } from "./$types";
  import { goto } from "$app/navigation";
  import { page } from "$app/state";
  import { WarningModal } from "$lib/ui";
  import { getExplorerRoute, getRouteSearchParams, getWorkspaceRoute } from "$lib/utils/routes";

  let { data }: PageProps = $props();

  let showNoRowModal = $state(false);

  $effect(() => {
    const bd = data.browserData;
    if (!bd?.id) {
      showNoRowModal = true;
      return;
    }
    showNoRowModal = false;
  });

  function updateSearchParams(updates: Record<string, string | undefined>) {
    const params = getRouteSearchParams(page.url);
    for (const [key, value] of Object.entries(updates)) {
      if (value === undefined || value === "") params.delete(key);
      else params.set(key, value);
    }
    return params.toString();
  }

  function navigateTable(updates: Record<string, string | undefined>) {
    const qs = updateSearchParams(updates);
    void goto(getExplorerRoute(data.dataset.id, qs), { replaceState: false, noScroll: true });
  }

  const handleSelectItem = async (itemId: string) => {
    await goto(getWorkspaceRoute(data.dataset.id, itemId));
  };
</script>

{#if data.browserData?.table_data}
  <DatasetExplorer
    selectedDataset={data.browserData}
    onSelectItem={handleSelectItem}
    onNavigate={navigateTable}
    pagination={data.pagination}
  />
{/if}
{#if showNoRowModal}
  <WarningModal
    message="No rows found. Keeping previous state."
    onConfirm={() => {
      showNoRowModal = false;
    }}
  />
{/if}
