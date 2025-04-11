<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { onDestroy } from "svelte";

  import type { DatasetBrowser } from "@pixano/core/src";
  import { getBrowser } from "@pixano/core/src/api";
  import WarningModal from "@pixano/core/src/components/modals/WarningModal.svelte";

  import DatasetExplorer from "../../../components/dataset/DatasetExplorer.svelte";
  import { goto } from "$app/navigation";
  import { page } from "$app/stores";
  import { datasetTableStore } from "$lib/stores/datasetStores";

  let selectedDatasetId: string;
  let selectedDataset: DatasetBrowser;
  let showNoRowModal = false;

  $: page.subscribe((value) => (selectedDatasetId = value.params.dataset));

  $: unsubscribe2datasetTableStore = datasetTableStore.subscribe((pagination) => {
    if (selectedDatasetId) {
      getBrowser(
        selectedDatasetId,
        pagination.currentPage,
        pagination.pageSize,
        pagination.query,
        pagination.where,
      )
        .then((datasetItems) => {
          if (datasetItems.id) {
            selectedDataset = datasetItems;
          } else {
            showNoRowModal = true;
            //do not change current selectedDataset if error / no row.
          }
        })
        .catch((err) => console.log("ERROR: Couldn't get dataset items", err));
    }
  });

  const handleSelectItem = async (event: CustomEvent) => {
    await goto(`/${selectedDataset.id}/dataset/${event.detail}`);
  };

  onDestroy(() => {
    unsubscribe2datasetTableStore();
  });
</script>

{#if selectedDataset?.table_data}
  <DatasetExplorer {selectedDataset} on:selectItem={handleSelectItem} />
{/if}
{#if showNoRowModal}
  <!-- TODO Manage filtered row count !
    -- but here we only have pagesize (20) rows, we don't know the real count.
    -- And back doesn't know either because it seek with limit=page_size
    -- Back should also launch a select COUNT() without limit to get the filtered count, and pass it in answer...
    -- so for now, we provide a warning when we go too far in pagination...
    -- At least, we should be able to avoid increasing the current page when it goes too far
  -->
  <WarningModal
    message="No rows found. Keeping previous state."
    details="Or no more rows in sub selelection."
    moreDetails=" (WARNING - UNDER DEVELOPMENT) Actually we don't get the total number of rows in filtered list. The current page may be wrong after this message."
    on:confirm={() => {
      showNoRowModal = false;
    }}
  />
{/if}
