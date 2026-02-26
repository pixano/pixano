<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import type { PageProps } from "./$types";
  import * as api from "$lib/api";
  import { WarningModal, type TableData, type TableRow } from "$lib/ui";

  import DatasetExplorer from "../../../components/dataset/DatasetExplorer.svelte";
  import { goto } from "$app/navigation";
  import { page } from "$app/state";
  import { COUNTS_COLUMNS_PREFIX } from "$lib/constants";
  import { getWorkspaceRoute } from "$lib/utils/routes";

  let { data }: PageProps = $props();

  let showNoRowModal = $state(false);

  // Enhance browser data with counts asynchronously
  let enhancedBrowserData = $state<typeof data.browserData>();

  $effect(() => {
    const bd = data.browserData;
    if (!bd?.id) {
      showNoRowModal = true;
      return;
    }
    showNoRowModal = false;
    enhancedBrowserData = bd;

    // Load counts asynchronously
    void getCounts(bd.id, bd.table_data)
      .then((tableCounts) => {
        enhancedBrowserData = { ...bd, table_data: tableCounts };
      })
      .catch((err) => {
        console.warn("Could not get computed items infos", err);
      });
  });

  const getCounts = async (datasetId: string, tableData: TableData) => {
    let extendedTableData = tableData;
    const page_item_ids = tableData.rows.map((row) => row.id as string);
    const counts = await api.getItemsInfo(datasetId, page_item_ids);
    const count_cols = [
      ...Object.keys(counts[0].info.entities),
      ...Object.keys(counts[0].info.annotations),
    ];

    extendedTableData.rows = tableData.rows.map((row) => {
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

  function updateSearchParams(updates: Record<string, string | undefined>) {
    const params = new URLSearchParams(page.url.searchParams);
    for (const [key, value] of Object.entries(updates)) {
      if (value === undefined || value === "") params.delete(key);
      else params.set(key, value);
    }
    return params.toString();
  }

  function navigateTable(updates: Record<string, string | undefined>) {
    const qs = updateSearchParams(updates);
    void goto(qs ? `?${qs}` : "?", { replaceState: false, noScroll: true });
  }

  const handleSelectItem = async (itemId: string) => {
    await goto(getWorkspaceRoute(data.dataset.id, itemId));
  };
</script>

{#if enhancedBrowserData?.table_data}
  <DatasetExplorer
    selectedDataset={enhancedBrowserData}
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
