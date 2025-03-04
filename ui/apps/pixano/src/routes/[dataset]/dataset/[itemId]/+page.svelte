<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import {
    api,
    BaseSchema,
    Entity,
    Image,
    PrimaryButton,
    SequenceFrame,
    WorkspaceType,
    type DatasetInfo,
    type DatasetItem,
    type FeaturesValues,
    type SaveItem,
    type Schema,
  } from "@pixano/core/src";
  import DatasetItemWorkspace from "@pixano/dataset-item-workspace/src/DatasetItemWorkspace.svelte";

  import {
    datasetSchema,
    datasetsStore,
    isLoadingNewItemStore,
    modelsStore,
    saveCurrentItemStore,
    sourcesStore,
  } from "../../../../lib/stores/datasetStores";
  import { goto } from "$app/navigation";
  import { page } from "$app/stores";

  let selectedItem: DatasetItem;
  let selectedDataset: DatasetInfo;
  let models: Array<string>;
  let currentDatasetId: string;
  let currentItemId: string;
  let isLoadingNewItem: boolean = false;
  let canSaveCurrentItem: boolean = false;
  let shouldSaveCurrentItem: boolean = false;
  let noItemFound: boolean = false;
  let featureValues: FeaturesValues = { main: {}, objects: {} };

  modelsStore.subscribe((value) => {
    models = value;
  });

  saveCurrentItemStore.subscribe((value) => {
    canSaveCurrentItem = value.canSave;
    shouldSaveCurrentItem = value.shouldSave;
  });

  $: saveCurrentItemStore.update((old) => ({ ...old, canSave: canSaveCurrentItem }));

  //TODO test quick & dirty -- WIP -- should use a common type from back & front
  // also should use zod, etc.
  type backFV = {
    name: string;
    restricted: boolean;
    values: string[];
  };
  type backFVS = Record<string, Record<string, backFV[]>>;

  const mapBackFeaturesValues2FrontFeaturesValues = (feature_values: backFVS) => {
    console.log("--- back feature_values", feature_values);
    /*
    --- current back format for features values (most probably to be changed)
    {
        "items": {}, //??
        "views": {},
        "entities": {"objects": [{"name": "category", "restricted": true, "values": ["rose", "orange"]}]},
        "annotations": {}
    }

    --- current front format for features values (probably to change also -- but it "works" with this)
    {
      "main": {
        "label": { "restricted": true, "values": ["nice", "very nice"] }
      },
      "objects": {
        "category_name": {"restricted": true, "values": ["rose", "orange"]}
    }
    */
    const frontFV: FeaturesValues = { main: {}, objects: {} };
    if ("items" in feature_values && feature_values["items"] && feature_values["items"]["items"]) {
      for (const feat of feature_values["items"]["items"]) {
        let { name, ...fv } = feat;
        frontFV.main[name] = fv;
      }
    }
    if (
      "entities" in feature_values &&
      feature_values["entities"] &&
      Object.keys(feature_values["entities"]).length > 0
    ) {
      for (const entity_group of $datasetSchema.groups.entities) {
        frontFV.objects = {};
        for (const feat of feature_values["entities"][entity_group]) {
          let { name, ...fv } = feat;
          frontFV.objects[name] = fv;
        }
      }
    }

    console.log("--- front feature_values", frontFV);
    return frontFV;
  };

  const handleSelectItem = (dataset: DatasetInfo, id: string) => {
    if (!dataset) return;
    api
      .getDataset(dataset.id)
      .then((ds) => {
        console.log("XXX handleSelectIem - Dataset:", ds);
        datasetSchema.set(ds.dataset_schema);
        featureValues = mapBackFeaturesValues2FrontFeaturesValues(ds.feature_values as backFVS);
        api
          .getDatasetItem(dataset.id, encodeURIComponent(id))
          .then((item) => {
            //if workspace type not defined, infer type from datasetItem content
            if (dataset.workspace === WorkspaceType.UNDEFINED) {
              for (const viewname in item.views) {
                if (Array.isArray(item.views[viewname])) {
                  dataset.workspace = WorkspaceType.VIDEO;
                  break;
                } else {
                  // VQA items have a "conversations" field in the entities
                  const is_vqa = "conversations" in item.entities;
                  if (is_vqa) {
                    dataset.workspace = WorkspaceType.IMAGE_VQA;
                    break;
                  } else {
                    dataset.workspace = WorkspaceType.IMAGE;
                  }
                }
              }
            }

            //append media_dir tu url + set image/sequence frame type (ui field)
            const media_dir = "media/";
            if (dataset.workspace === WorkspaceType.VIDEO) {
              for (const viewname in item.views) {
                let view = item.views[viewname];
                if (Array.isArray(view)) {
                  const video = view as SequenceFrame[];
                  video.forEach((sf) => {
                    sf.data.type = WorkspaceType.VIDEO;
                    sf.data.url = media_dir + sf.data.url;
                  });
                  video.sort((a, b) => a.data.frame_index - b.data.frame_index);
                } else {
                  throw Error("Video workspace without SequenceFrames.");
                }
              }
            }
            if (
              dataset.workspace === WorkspaceType.IMAGE ||
              dataset.workspace === WorkspaceType.IMAGE_VQA
            ) {
              for (const viewname in item.views) {
                let view = item.views[viewname];
                if (Array.isArray(view)) {
                  throw Error("Not video workspace with SequenceFrames.");
                } else {
                  const image = view as Image;
                  image.data.type = WorkspaceType.IMAGE;
                  image.data.url = media_dir + image.data.url;
                }
              }
            }
            selectedItem = item;
            selectedItem.ui = { type: dataset.workspace, datasetId: dataset.id };
            if (Object.keys(selectedItem).length === 0) {
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
      api
        .getSources(selectedDataset.id)
        .then((sources) => sourcesStore.set(sources))
        .catch((err) => console.error("ERROR: Unable to get sources", err));
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

  function reduceByTypeAndGroupAndTable(
    data: SaveItem[],
    type: string,
  ): Record<string, Record<string, (Schema | string)[]>> {
    const type_data = data.filter((d) => d.change_type === type);
    return type_data.reduce(
      (acc, item) => {
        const group = item.object.table_info.group;
        const table = item.object.table_info.name;
        if (!acc[group]) {
          acc[group] = {};
        }
        if (!acc[group][table]) {
          acc[group][table] = [];
        }
        if (type === "delete") {
          acc[group][table].push(item.object.id);
        } else {
          //remove ui field  ('ui' is not used, it's OK -- so we disable linters for the line)
          // @ts-expect-error Property ui may not exist, but we don't care as we don't use it
          const { ui, ...bodyObj } = item.object; // eslint-disable-line @typescript-eslint/no-unused-vars
          acc[group][table].push(bodyObj as Schema);
        }
        return acc;
      },
      {} as Record<string, Record<string, (Schema | string)[]>>,
    );
  }

  async function handleSaveItem(data: SaveItem[]) {
    //entities first to avoid database consistency checks issues
    data.sort((a, b) => {
      const priority = (object: Schema) => {
        // Highest priority: Track
        if (object.table_info.base_schema === BaseSchema.Track) return 0;
        // Second priority : Entity as top entity
        if (object.table_info.base_schema === BaseSchema.Entity) {
          if ((object as Entity).data.parent_ref.id === "") return 1;
          else return 2; //Third priority: Entity as sub entity
        }
        return 3; // Lowest priority
      };
      return priority(a.object) - priority(b.object);
    });

    //gather adds by group and table
    const add_data_by_group_and_table = reduceByTypeAndGroupAndTable(data, "add");
    for (const group in add_data_by_group_and_table) {
      for (const [table, schs] of Object.entries(add_data_by_group_and_table[group])) {
        let no_table = false;
        let route = group;
        if (route === "item") {
          route = "items";
          no_table = true;
        }
        if (route === "source") {
          route = "sources";
          no_table = true;
        }
        await api.addSchemas(route, selectedDataset.id, schs as Schema[], table, no_table);
      }
    }

    //gather updates by group and table
    const update_data_by_group_and_table = reduceByTypeAndGroupAndTable(data, "update");
    for (const group in update_data_by_group_and_table) {
      for (const [table, schs] of Object.entries(update_data_by_group_and_table[group])) {
        let no_table = false;
        let route = group;
        if (route === "item") {
          route = "items";
          no_table = true;
        }
        if (route === "source") {
          route = "sources";
          no_table = true;
        }
        await api.updateSchemas(route, selectedDataset.id, schs as Schema[], table, no_table);
      }
    }

    //gather deletes by group and table
    const delete_ids_by_group_and_table = reduceByTypeAndGroupAndTable(data, "delete");
    for (const group in delete_ids_by_group_and_table) {
      for (const [table, ids] of Object.entries(delete_ids_by_group_and_table[group])) {
        let no_table = false;
        let route = group;
        if (route === "item") {
          route = "items";
          no_table = true;
        }
        await api.deleteSchemasByIds(route, selectedDataset.id, ids as string[], table, no_table);
      }
    }

    saveCurrentItemStore.update((old) => ({ ...old, shouldSave: false }));
  }
</script>

{#if selectedItem && selectedDataset}
  <DatasetItemWorkspace
    {selectedItem}
    {models}
    {featureValues}
    {handleSaveItem}
    isLoading={isLoadingNewItem}
    bind:canSaveCurrentItem
    {shouldSaveCurrentItem}
  />
{/if}
{#if !selectedItem && noItemFound}
  <div class="w-full pt-40 text-center flex flex-col gap-5 items-center">
    <p>Current item could not be loaded</p>
    <PrimaryButton on:click={() => goto(`/${currentDatasetId}/dataset`)}>
      Back to dataset
    </PrimaryButton>
  </div>
{/if}
