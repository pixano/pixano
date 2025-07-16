<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { onDestroy, onMount } from "svelte";
  import type { Unsubscriber } from "svelte/motion";

  import { api, type DatasetBrowser, type TableData, type TableRow } from "@pixano/core/src";
  import { getBrowser } from "@pixano/core/src/api";
  import WarningModal from "@pixano/core/src/components/modals/WarningModal.svelte";

  import DatasetExplorer from "../../../components/dataset/DatasetExplorer.svelte";
  import { goto } from "$app/navigation";
  import { page } from "$app/stores";
  import { datasetItemIds, datasetTableStore } from "$lib/stores/datasetStores";
    import { COUNTS_COLUMNS_PREFIX } from "$lib/constants/pixanoConstants";

  let selectedDataset: DatasetBrowser;
  let showNoRowModal = false;

  const getCounts = async (datasetId: string, tableData: TableData) => {
    let extendedTableData = tableData;
    //retrieve objects counts
    const page_item_ids = tableData.rows.map((row) => row.id as string);
    const counts = await api.getItemsInfo(datasetId, page_item_ids);
    const count_cols = [
      ...Object.keys(counts[0].info.entities),
      ...Object.keys(counts[0].info.annotations),
    ];

    extendedTableData.rows = tableData.rows.map((row) => {
      //tableData.rows = tableData.rows.map((row) => {
      let count = counts.find((count) => row.id === count.id);
      if (count) {
        const count_ent_cells = Object.fromEntries(
          Object.entries(count.info.entities).map(([table, val]) => [
            `${COUNTS_COLUMNS_PREFIX}${table}`,
            val.count,
          ]),
        );
        const count_ann_cells = Object.fromEntries(
          Object.entries(count.info.annotations).map(([table, val]) => [
            `${COUNTS_COLUMNS_PREFIX}${table}`,
            val.count,
          ]),
        );
        return { ...row, ...count_ent_cells, ...count_ann_cells } as TableRow;
      }
      return row;
    });
    extendedTableData.columns = [
      ...tableData.columns,
      ...count_cols.map((table) => ({ name: `${COUNTS_COLUMNS_PREFIX}${table}`, type: "int" })),
    ];
    return extendedTableData;
  };

  let unsubscribe2datasetTableStore: Unsubscriber;
  onMount(async () => {
    unsubscribe2datasetTableStore = datasetTableStore.subscribe((pagination) => {
      if ($page.params.dataset) {
        getBrowser(
          $page.params.dataset,
          pagination.currentPage,
          pagination.pageSize,
          pagination.query,
          pagination.where,
        )
          .then((datasetItems) => {
            if (datasetItems.id) {
              getCounts(datasetItems.id, datasetItems.table_data).then((table_counts) => {
                selectedDataset = datasetItems;
                selectedDataset.table_data = table_counts;
                datasetItemIds.set(selectedDataset.item_ids);
                selectedDataset.pagination.total_size = selectedDataset.item_ids.length;
              });
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
