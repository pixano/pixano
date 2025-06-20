<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { onDestroy, onMount } from "svelte";
  import type { Unsubscriber } from "svelte/motion";

  import type { DatasetBrowser } from "@pixano/core/src";
  import { getBrowser } from "@pixano/core/src/api";
  import WarningModal from "@pixano/core/src/components/modals/WarningModal.svelte";

  import DatasetExplorer from "../../../components/dataset/DatasetExplorer.svelte";
  import { goto } from "$app/navigation";
  import { page } from "$app/stores";
  import { datasetItemIds, datasetTableStore } from "$lib/stores/datasetStores";

  let selectedDatasetId: string;
  let selectedDataset: DatasetBrowser;
  let showNoRowModal = false;

  $: page.subscribe((value) => (selectedDatasetId = value.params.dataset));

  let unsubscribe2datasetTableStore: Unsubscriber;
  onMount(() => {
    unsubscribe2datasetTableStore = datasetTableStore.subscribe((pagination) => {
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
              datasetItemIds.set(selectedDataset.item_ids);
              selectedDataset.pagination.total_size = selectedDataset.item_ids.length;
            } else {
              showNoRowModal = true;
              //do not change current selectedDataset if error / no row.
            }
          })
          .catch((err) => console.log("ERROR: Couldn't get dataset items", err));
      }
    });
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
  <WarningModal
    message="No rows found. Keeping previous state."
    on:confirm={() => {
      showNoRowModal = false;
    }}
  />
{/if}
