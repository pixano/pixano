<script lang="ts">
  import { Check } from "lucide-svelte";
  import { Command, cn } from "@pixano/core/src";
  import { tick } from "svelte";

  export let listItems: { value: string; label: string }[] = [];
  export let placeholder: string = "Select an item";

  let open = false;
  let inputValue: string = "";
  export let value: string = "";
  export let saveValue: (value: string) => void = () => {};

  $: selectedValue = listItems.find((f) => f.value === value)?.label ?? placeholder;

  $: console.log({ value, inputValue, selectedValue, listItems });

  $: {
    if (value) saveValue(value);
  }

  // We want to refocus the trigger button when the user selects
  // an item from the list so users can continue navigating the
  // rest of the form with the keyboard.
  function closeAndFocusTrigger(triggerId: string) {
    open = false;
    tick()
      .then(() => {
        document.getElementById(triggerId)?.focus();
      })
      .catch((err) => console.error(err));
  }

  const onValidation = (value: string) => {
    selectedValue = value;
    open = false;
  };

  const onSelect = (currentValue: string) => {
    value = currentValue;
    closeAndFocusTrigger("ids.trigger");
  };
</script>

<Command.Root class="overflow-visible">
  <Command.Input
    {onValidation}
    bind:value={inputValue}
    placeholder="Search framework..."
    class="h-9"
    on:focus={() => {
      console.log("focus");
      open = true;
    }}
  />

  <!-- <input class="h-9" placeholder="Search" bind:value={inputValue} /> -->
  <!--<Command.Empty>No framework found.</Command.Empty>-->
  {#if open}
    <Command.Group class="z-10 bg-white absolute top-full w-full">
      {#each listItems as val}
        <Command.Item value={val.value} {onSelect}>
          <Check class={cn("mr-2 h-4 w-4", value !== val.value && "text-transparent")} />
          {val.label}
        </Command.Item>
      {/each}
    </Command.Group>
  {/if}
</Command.Root>

<!--
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
  -->
