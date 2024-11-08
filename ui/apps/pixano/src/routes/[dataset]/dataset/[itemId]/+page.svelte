<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { page } from "$app/stores";
  import {
    type DatasetItem,
    type DatasetInfo,
    type SaveItem,
    PrimaryButton,
    type Schema,
  } from "@pixano/core/src";
  import DatasetItemWorkspace from "@pixano/dataset-item-workspace/src/DatasetItemWorkspace.svelte";
  import { api } from "@pixano/core/src";
  import {
    datasetsStore,
    datasetSchema,
    isLoadingNewItemStore,
    modelsStore,
    saveCurrentItemStore,
  } from "../../../../lib/stores/datasetStores";
  import { goto } from "$app/navigation";

  let selectedItem: DatasetItem;
  let selectedDataset: DatasetInfo;
  let models: Array<string>;
  let currentDatasetId: string;
  let currentItemId: string;
  let isLoadingNewItem: boolean = false;
  let canSaveCurrentItem: boolean = false;
  let shouldSaveCurrentItem: boolean = false;
  let noItemFound: boolean = false;

  modelsStore.subscribe((value) => {
    models = value;
  });

  saveCurrentItemStore.subscribe((value) => {
    canSaveCurrentItem = value.canSave;
    shouldSaveCurrentItem = value.shouldSave;
  });

  $: saveCurrentItemStore.update((old) => ({ ...old, canSave: canSaveCurrentItem }));

  const handleSelectItem = (dataset: DatasetInfo, id: string) => {
    if (!dataset) return;
    api
      .getDataset(dataset.id)
      .then((ds) => {
        datasetSchema.set(ds.dataset_schema);
        api
          .getDatasetItem(dataset.id, encodeURIComponent(id))
          .then((item) => {
            let item_type: "image" | "video" | "3d" = "image";
            const media_dir = "media/";
            Object.values(item.views).map((view) => {
              if (Array.isArray(view)) {
                const video = view;
                item_type = "video";
                video.forEach((sf) => {
                  sf.data.type = "video";
                  sf.data.url = media_dir + sf.data.url;
                });
                video.sort((a, b) => a.data.frame_index - b.data.frame_index);
              } else {
                const image = view;
                image.data.type = "image";
                image.data.url = media_dir + image.data.url;
              }
              return view;
            });
            selectedItem = item;
            selectedItem.ui = { type: item_type, datasetId: dataset.id };
            if (Object.keys(item).length === 0) {
              noItemFound = true;
            } else {
              noItemFound = false;
            }
            console.log("XXX handleSelectIem - selectedItem:", selectedItem);
          })
          .then(() => isLoadingNewItemStore.set(false))
          .catch((err) => console.error(err));
      })
      .catch((err) => console.error(err));
  };

  page.subscribe((value) => {
    currentDatasetId = value.params.dataset;
    currentItemId = value.params.itemId;
  });

  datasetsStore.subscribe((value) => {
    const foundDataset = value?.find((dataset) => dataset.id === currentDatasetId);
    if (foundDataset) {
      selectedDataset = foundDataset;
    }
  });

  $: {
    if (currentItemId !== selectedItem?.item.id) {
      isLoadingNewItemStore.set(true);
      handleSelectItem(selectedDataset, currentItemId);
    }
  }

  $: isLoadingNewItemStore.subscribe((value) => {
    isLoadingNewItem = value;
  });

  async function handleSaveItem(data: SaveItem[]) {
    //entities first to avoid database consistency checks issues
    data.sort((a, b) => {
      if (
        ["Entity", "Track"].includes(a.object.table_info.base_schema) &&
        !["Entity", "Track"].includes(b.object.table_info.base_schema)
      )
        return -1;
      else if (
        !["Entity", "Track"].includes(a.object.table_info.base_schema) &&
        ["Entity", "Track"].includes(b.object.table_info.base_schema)
      )
        return 1;
      else return 0;
    });

    const no_delete_data = data.filter((d) => d.change_type !== "delete");
    for (const savedItem of no_delete_data) {
      let no_table = false;
      let route = savedItem.object.table_info.group;
      if (route === "item") {
        route = "items";
        no_table = true;
      }
      //remove ui field  ('ui' is not used, it's OK -- so we disable linters for the line)
      // @ts-expect-error Property ui may not exist, but we don't care as we don't use it
      const { ui, ...bodyObj } = savedItem.object; // eslint-disable-line @typescript-eslint/no-unused-vars
      if (savedItem.change_type === "add") {
        await api.addSchema(route, selectedDataset.id, bodyObj as Schema, no_table);
      }
      if (savedItem.change_type === "update") {
        await api.updateSchema(route, selectedDataset.id, bodyObj as Schema, no_table);
      }
    }
    //gather deletes by group and table
    //-- if we delete a track, there is many things to delete, so it's more efficient to delete them all at once
    const delete_data = data.filter((d) => d.change_type === "delete");
    const delete_ids_by_group_and_table = delete_data.reduce(
      (acc, item) => {
        const group = item.object.table_info.group;
        const table = item.object.table_info.name;
        if (!acc[group]) {
          acc[group] = {};
        }
        if (!acc[group][table]) {
          acc[group][table] = [];
        }
        acc[group][table].push(item.object.id);
        return acc;
      },
      {} as Record<string, Record<string, string[]>>,
    );
    for (const group in delete_ids_by_group_and_table) {
      for (const [table, ids] of Object.entries(delete_ids_by_group_and_table[group])) {
        let no_table = false;
        let route = group;
        if (route === "item") {
          route = "items";
          no_table = true;
        }
        await api.deleteSchemasByIds(route, selectedDataset.id, ids, table, no_table);
      }
    }
    saveCurrentItemStore.update((old) => ({ ...old, shouldSave: false }));
  }
</script>

{#if selectedItem && selectedDataset}
  <div class="pt-20 h-1 min-h-screen">
    <DatasetItemWorkspace
      {selectedItem}
      {models}
      featureValues={{ main: {}, objects: {} }}
      {handleSaveItem}
      isLoading={isLoadingNewItem}
      bind:canSaveCurrentItem
      {shouldSaveCurrentItem}
      headerHeight={80}
    />
  </div>
{/if}
{#if !selectedItem && noItemFound}
  <div class="w-full pt-40 text-center flex flex-col gap-5 items-center">
    <p>Current item could not be loaded</p>
    <PrimaryButton on:click={() => goto(`/${currentDatasetId}/dataset`)}>
      Back to dataset
    </PrimaryButton>
  </div>
{/if}
