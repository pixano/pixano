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
  import {
    getExplorerRoute,
    getRouteSearchParams,
    getWorkspaceRoute,
    pickExplorerQuery,
  } from "$lib/utils/routes";

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

  function updateSearchParams(updates: Record<string, string | string[] | undefined>) {
    const params = getRouteSearchParams(page.url);
    for (const [key, value] of Object.entries(updates)) {
      params.delete(key);
      if (value === undefined || value === "") continue;
      if (Array.isArray(value)) {
        for (const item of value) if (item !== "") params.append(key, item);
      } else {
        params.set(key, value);
      }
    }
    return params.toString();
  }

  function navigateTable(updates: Record<string, string | string[] | undefined>) {
    const qs = updateSearchParams(updates);
    void goto(getExplorerRoute(data.dataset.id, qs), { replaceState: false, noScroll: true });
  }

  const handleSelectItem = async (itemId: string) => {
    // Carry the active filter/sort/search into the workspace so item-to-item
    // navigation stays within the current result set.
    const query = pickExplorerQuery(getRouteSearchParams(page.url)).toString();
    await goto(getWorkspaceRoute(data.dataset.id, itemId, query));
  };
</script>

{#if data.browserData?.table_data}
  <DatasetExplorer
    selectedDataset={data.browserData}
    filterSchema={data.filterSchema}
    semanticActive={data.semantic?.active ?? false}
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
