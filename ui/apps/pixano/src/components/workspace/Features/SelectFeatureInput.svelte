<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { Select } from "bits-ui";
  import { Check, ChevronsUpDown } from "lucide-svelte";

  import type { ListFeature } from "$lib/types/workspace";

  interface Props {
    listFeature: Pick<ListFeature, "name" | "value" | "options">;
    isEditing: boolean;
    handleInputChange: (value: string, propertyName: string) => void;
  }

  let { listFeature, isEditing, handleInputChange }: Props = $props();

  const listItems = $derived(
    (listFeature.options ?? []).map((option) => ({
      value: option.value ?? "",
      label: option.label ?? option.value ?? "",
    })),
  );
</script>

{#if isEditing}
  <Select.Root
    type="single"
    value={listFeature.value}
    onValueChange={(v) => handleInputChange(v, listFeature.name)}
    items={listItems}
  >
    <Select.Trigger
      class="justify-between h-10 px-4 py-2 border border-input rounded-md bg-background text-sm inline-flex items-center w-[200px]"
    >
      {#snippet children({ selectedLabel })}
        {selectedLabel || `Select a ${listFeature.name}`}
        <ChevronsUpDown class="ml-2 h-4 w-4 shrink-0 opacity-50" />
      {/snippet}
    </Select.Trigger>
    <Select.Portal>
      <Select.Content
        class="z-50 rounded-md border bg-popover p-1 text-popover-foreground shadow-md"
      >
        {#each listItems as item}
          <Select.Item
            value={item.value}
            label={item.label}
            class="flex items-center gap-2 rounded-sm px-2 py-1.5 text-sm cursor-pointer data-[highlighted]:bg-accent data-[highlighted]:text-accent-foreground"
          >
            <Check class="h-4 w-4 {listFeature.value !== item.value ? 'text-transparent' : ''}" />
            {item.label}
          </Select.Item>
        {/each}
      </Select.Content>
    </Select.Portal>
  </Select.Root>
{:else if listFeature.value}
  <p class="first-letter:uppercase">
    {listFeature.value}
  </p>
{/if}
