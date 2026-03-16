<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { Command, Popover } from "bits-ui";
  import { Check } from "phosphor-svelte";
  import { tick } from "svelte";

  import { cn } from "$lib/ui";

  interface Props {
    onTextInputChange: (value: string) => void;
    featureList?: { value: string; label: string; isTemp?: boolean }[];
    placeholder?: string;
    value?: string;
    autofocus?: boolean;
    className?: string;
    isInputEnabled?: boolean;
  }

  let {
    onTextInputChange,
    featureList = $bindable([]),
    placeholder = "Select a feature",
    value = $bindable(""),
    autofocus = false,
    className = "",
    isInputEnabled = true,
  }: Props = $props();

  let open = $state(false);
  let selectedValue = $state<string | null>(null);
  let inputValue: string = $state("");
  const triggerId = `autocomplete-feature-${Math.random().toString(36).slice(2, 11)}`;

  $effect(() => {
    open = autofocus;
  });

  $effect(() => {
    inputValue = value;
  });

  $effect(() => {
    selectedValue =
      featureList.find((f) => f.value === value)?.label ??
      (value === "" ? null : value) ??
      placeholder;
  });

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
    const existingValue = featureList.find((f) => f.value === inputValue)?.label;
    if (!existingValue && inputValue) {
      featureList = [...featureList, { value: inputValue, label: inputValue }];
    }
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

<Popover.Root bind:open>
  <Popover.Trigger
    type="button"
    id={triggerId}
    class={cn(
      "py-0 rounded-md bg-transparent flex h-10 items-center border border-input bg-card px-3 text-sm ring-offset-background w-full",
      className,
    )}
  >
    {selectedValue}
  </Popover.Trigger>
  <Popover.Content
    class="z-50 rounded-md border bg-popover p-0 text-popover-foreground shadow-md outline-none"
    tabindex={-1}
  >
    <Command.Root>
      {#if isInputEnabled}
        <Command.Input {placeholder} bind:value={inputValue} oninput={onSearchInput} />
      {/if}
      <Command.List>
        {#each featureList as feature}
          <Command.Item value={feature.value} onSelect={() => onSelect(feature.value, triggerId)}>
            <Check class={cn("mr-2 h-4 w-4", value !== feature.value && "text-transparent")} />
            {feature.label}
          </Command.Item>
        {/each}
      </Command.List>
    </Command.Root>
  </Popover.Content>
</Popover.Root>
