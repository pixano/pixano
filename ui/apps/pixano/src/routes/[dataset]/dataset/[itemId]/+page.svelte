<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import * as api from "$lib/api";
  import {
    BaseSchema,
    Entity,
    PrimaryButton,
    effectProbe,
    type SaveItem,
    type Schema,
  } from "$lib/ui";
  import { canSave } from "$lib/stores/workspaceStores.svelte";
  import WorkspaceShell from "../../../../components/workspace/WorkspaceShell.svelte";
  import { resolveWorkspaceVariant } from "../../../../components/workspace/workspaceRegistry";

  import { saveCurrentItemStore } from "$lib/stores/appStores.svelte";
  import { goto } from "$app/navigation";
  import { navigating } from "$app/state";
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

  function reduceByTypeAndGroupAndTable(
    saveData: SaveItem[],
    type: string,
  ): Record<string, Record<string, (Schema | string)[]>> {
    const type_data = saveData.filter((d) => d.change_type === type);
    return type_data.reduce(
      (acc, item) => {
        const group = item.data.table_info.group;
        const table = item.data.table_info.name;
        if (!acc[group]) {
          acc[group] = {};
        }
        if (!acc[group][table]) {
          acc[group][table] = [];
        }
        if (type === "delete") {
          acc[group][table].push(item.data.id);
        } else {
          //remove ui field  ('ui' is not used, it's OK -- so we disable linters for the line)
          // @ts-expect-error Property ui may not exist, but we don't care as we don't use it
          const { ui, ...bodyObj } = item.data; // eslint-disable-line @typescript-eslint/no-unused-vars
          acc[group][table].push(bodyObj as Schema);
        }
        return acc;
      },
      {} as Record<string, Record<string, (Schema | string)[]>>,
    );
  }

  async function handleSaveItem(saveData: SaveItem[]) {
    //entities first to avoid database consistency checks issues
    saveData.sort((a, b) => {
      const priority = (object: Schema) => {
        if (object.table_info.base_schema === BaseSchema.Track) return 0;
        if (object.table_info.base_schema === BaseSchema.Entity) {
          if ((object as Entity).data.parent_id === "") return 1;
          else return 2;
        }
        return 3;
      };
      return priority(a.data) - priority(b.data);
    });

    const add_data_by_group_and_table = reduceByTypeAndGroupAndTable(saveData, "add");
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
        await api.addSchemas(route, data.dataset.id, schs as Schema[], table, no_table);
      }
    }

    const update_data_by_group_and_table = reduceByTypeAndGroupAndTable(saveData, "update");
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
        await api.updateSchemas(route, data.dataset.id, schs as Schema[], table, no_table);
      }
    }

    const delete_ids_by_group_and_table = reduceByTypeAndGroupAndTable(saveData, "delete");
    for (const group in delete_ids_by_group_and_table) {
      for (const [table, ids] of Object.entries(delete_ids_by_group_and_table[group])) {
        let no_table = false;
        let route = group;
        if (route === "item") {
          route = "items";
          no_table = true;
        }
        await api.deleteSchemasByIds(route, data.dataset.id, ids as string[], table, no_table);
      }
    }

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
    <PrimaryButton onclick={() => goto(`/${data.dataset.id}/dataset`)}>
      Back to dataset
    </PrimaryButton>
  </div>
{/if}
