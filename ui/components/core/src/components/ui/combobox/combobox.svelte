<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { Check, ChevronsUpDown } from "lucide-svelte";
  import { tick } from "svelte";

  import { cn } from "../../../lib/utils/styleUtils";
  import { Button } from "../button";
  import * as Command from "../command";
  import * as Popover from "../popover";

  export let listItems: { value: string; label: string }[] = [];
  export let placeholder: string = "Select an item";

  let open = false;
  export let value: string = "";
  export let saveValue: (value: string) => void = () => {};
  export let width: string = "w-[200px]";

  $: selectedValue = listItems.find((f) => f.value === value)?.label ?? placeholder;

  $: {
    if (value) saveValue(value);
  }

  // We want to refocus the trigger button when the user selects
  // an item from the list so users can continue navigating the
  // rest of the form with the keyboard.
  function closeAndFocusTrigger(triggerId: string) {
    open = false;
    tick().then(
      () => {
        document.getElementById(triggerId)?.focus();
      },
      () => {},
    );
  }
</script>

<Popover.Root bind:open let:ids>
  <Popover.Trigger asChild let:builder>
    <Button
      builders={[builder]}
      variant="outline"
      role="combobox"
      aria-expanded={open}
      class={cn("justify-between", width)}
    >
      {selectedValue}
      <ChevronsUpDown class="ml-2 h-4 w-4 shrink-0 opacity-50" />
    </Button>
  </Popover.Trigger>
  <Popover.Content class={cn("p-0", width)}>
    <Command.Root>
      <Command.Group>
        {#each listItems as listItem}
          <Command.Item
            value={listItem.value}
            onSelect={(currentValue) => {
              value = currentValue;
              closeAndFocusTrigger(ids.trigger);
            }}
          >
            <Check class={cn("mr-2 h-4 w-4", value !== listItem.value && "text-transparent")} />
            {listItem.label}
          </Command.Item>
        {/each}
      </Command.Group>
    </Command.Root>
  </Popover.Content>
</Popover.Root>
