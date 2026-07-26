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
    // eslint-disable-next-line @typescript-eslint/no-unsafe-assignment
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
      "flex h-10 w-full items-center rounded-xl border border-input bg-background px-3 text-sm text-foreground shadow-sm transition-colors hover:bg-accent/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
      className,
    )}
  >
    {selectedValue}
  </Popover.Trigger>
  <Popover.Content
    sideOffset={6}
    class="z-50 w-[var(--bits-floating-anchor-width)] rounded-2xl border border-border/50 bg-popover/95 p-1.5 text-popover-foreground shadow-elevation-2 outline-none backdrop-blur-md"
    tabindex={-1}
  >
    <Command.Root>
      {#if isInputEnabled}
        <Command.Input
          {placeholder}
          bind:value={inputValue}
          oninput={onSearchInput}
          class="mb-1 h-9 w-full rounded-lg border border-input bg-background px-2.5 text-sm text-foreground placeholder:text-muted-foreground/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        />
      {/if}
      <Command.List>
        {#each featureList as feature}
          <Command.Item
            value={feature.value}
            onSelect={() => onSelect(feature.value, triggerId)}
            class="flex cursor-pointer items-center rounded-lg px-2 py-1.5 text-sm outline-none transition-colors data-[selected]:bg-accent data-[selected]:text-accent-foreground"
          >
            <Check class={cn("mr-2 h-4 w-4", value !== feature.value && "text-transparent")} />
            {feature.label}
          </Command.Item>
        {/each}
      </Command.List>
    </Command.Root>
  </Popover.Content>
</Popover.Root>
