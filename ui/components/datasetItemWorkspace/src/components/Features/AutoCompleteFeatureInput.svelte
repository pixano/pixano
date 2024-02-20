<script lang="ts">
  // import { Check } from "lucide-svelte";
  // import { Command, cn, Popover } from "@pixano/core/src";

  // export let featureList: { value: string; label: string }[] = [];

  // export let isFixed: boolean = false;

  // let open = false;

  // const onSelect = (currentValue: string) => {
  //   value = currentValue;
  //   onTextInputChange(value);
  //   open = false;
  // };

  import { Check } from "lucide-svelte";
  import { tick } from "svelte";
  import { Command, cn, Popover } from "@pixano/core/src";

  export let onTextInputChange: (value: string) => void;
  export let featureList: { value: string; label: string; isTemp?: boolean }[] = [];
  export let placeholder: string = "Select a feature";
  export let value: string = "";
  export let autofocus: boolean = false;
  export let className = "";

  let open = autofocus;
  let selectedValue = value || placeholder;
  let inputValue: string = value;

  $: selectedValue = featureList.find((f) => f.value === value)?.label ?? placeholder;

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

  const onSelect = (currentValue: string, trigger: string) => {
    value = currentValue;
    onTextInputChange(value);
    closeAndFocusTrigger(trigger);
  };

  const onSearchInput = () => {
    const existingValue = featureList.find((f) => f.value === inputValue)?.label;
    if (!existingValue && inputValue) {
      featureList = [...featureList, { value: inputValue, label: inputValue }];
    }
  };
</script>

<Popover.Root bind:open let:ids>
  <Popover.Trigger asChild let:builder>
    <button
      type="button"
      use:builder.action
      {...builder}
      class={cn(
        "py-0 rounded-md bg-transparent flex h-10 items-center border border-input bg-white px-3 text-sm ring-offset-background w-full",
        className,
      )}
    >
      {selectedValue}
    </button>
  </Popover.Trigger>
  <Popover.Content class="p-0 " tabindex={-1}>
    <Command.Root>
      <Command.Input
        {placeholder}
        on:change={() => console.log("changed")}
        bind:value={inputValue}
        on:input={onSearchInput}
      />
      <Command.List>
        {#each featureList as feature}
          <Command.Item
            value={feature.value}
            onSelect={(currentValue) => onSelect(currentValue, ids.trigger)}
          >
            <Check class={cn("mr-2 h-4 w-4", value !== feature.value && "text-transparent")} />
            {feature.label}
          </Command.Item>
        {/each}
      </Command.List>
    </Command.Root>
  </Popover.Content>
</Popover.Root>
