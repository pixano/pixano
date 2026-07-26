<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { Combobox } from "bits-ui";
  import { CaretUpDown, Check, Plus } from "phosphor-svelte";
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
    placeholder = "",
    value = $bindable(""),
    autofocus = false,
    className = "",
    isInputEnabled = true,
  }: Props = $props();

  let open = $state(false);
  let search = $state("");
  let inputRef = $state<HTMLInputElement | null>(null);

  const effectivePlaceholder = $derived(
    placeholder || (isInputEnabled ? "Type or choose…" : "Choose a value…"),
  );

  // Free text is allowed (unless restricted); filter as the user types.
  const filtered = $derived(
    search === "" || !isInputEnabled
      ? featureList
      : featureList.filter((f) => f.label.toLowerCase().includes(search.toLowerCase())),
  );
  const hasExactMatch = $derived(
    featureList.some((f) => f.value.toLowerCase() === search.trim().toLowerCase()),
  );
  const createCandidate = $derived(
    isInputEnabled && search.trim() !== "" && !hasExactMatch ? search.trim() : null,
  );

  /** Commit a value: update the bound value, register it once, notify, sync the input. */
  function commit(next: string) {
    value = next;
    if (next !== "" && !featureList.some((f) => f.value === next)) {
      featureList = [...featureList, { value: next, label: next }];
    }
    onTextInputChange(next);
    if (inputRef) inputRef.value = next;
    search = "";
  }

  // Reflect externally-set values into the input (without clobbering active typing).
  $effect(() => {
    if (inputRef && document.activeElement !== inputRef) {
      inputRef.value = value;
    }
  });

  // Autofocus focuses the input — it must NOT auto-open the list.
  $effect(() => {
    if (autofocus && inputRef) {
      void tick().then(() => inputRef?.focus());
    }
  });

  function handleBlur() {
    // Committing typed free text on blur lets Tab-through work like a tag editor.
    const text = search.trim();
    if (!open && isInputEnabled && text !== "" && text !== value) {
      commit(text);
    }
  }
</script>

<Combobox.Root
  type="single"
  bind:open
  value={value === "" ? undefined : value}
  onValueChange={(next) => {
    if (next !== undefined) commit(next);
  }}
  onOpenChange={(isOpen) => {
    if (!isOpen) search = "";
  }}
>
  <div class={cn("relative w-full", className)}>
    <Combobox.Input
      bind:ref={inputRef}
      defaultValue={value}
      readonly={!isInputEnabled}
      placeholder={effectivePlaceholder}
      aria-label={effectivePlaceholder}
      oninput={(event) => {
        search = event.currentTarget.value;
        if (!open) open = true;
      }}
      onblur={handleBlur}
      class={cn(
        "h-10 w-full rounded-xl border border-input bg-background px-3 pr-9 text-sm text-foreground",
        "placeholder:text-muted-foreground/60 shadow-sm transition-colors",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        !isInputEnabled && "cursor-pointer",
      )}
    />
    <Combobox.Trigger
      aria-label="Show values"
      class="absolute right-1.5 top-1/2 -translate-y-1/2 inline-flex h-7 w-7 items-center justify-center rounded-lg text-muted-foreground hover:bg-accent hover:text-foreground transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
    >
      <CaretUpDown size={14} />
    </Combobox.Trigger>
  </div>
  <Combobox.Portal>
    <Combobox.Content
      sideOffset={6}
      class="z-50 max-h-64 overflow-y-auto rounded-2xl border border-border/50 bg-popover/95 p-1.5 text-popover-foreground shadow-elevation-2 backdrop-blur-md w-[var(--bits-floating-anchor-width)]"
    >
      {#each filtered as feature, i (feature.value + "\u0000" + i)}
        <Combobox.Item
          value={feature.value}
          label={feature.label}
          class="flex cursor-pointer items-center gap-2 rounded-lg px-2.5 py-1.5 text-sm outline-none transition-colors data-[highlighted]:bg-accent data-[highlighted]:text-accent-foreground"
        >
          <Check
            size={13}
            class={cn("shrink-0", value === feature.value ? "text-primary" : "text-transparent")}
          />
          <span class="truncate">{feature.label}</span>
        </Combobox.Item>
      {/each}
      {#if createCandidate !== null}
        <Combobox.Item
          value={createCandidate}
          label={createCandidate}
          class="flex cursor-pointer items-center gap-2 rounded-lg px-2.5 py-1.5 text-sm outline-none transition-colors data-[highlighted]:bg-accent data-[highlighted]:text-accent-foreground"
        >
          <Plus size={13} class="shrink-0 text-primary" />
          <span class="truncate">Create "{createCandidate}"</span>
        </Combobox.Item>
      {/if}
      {#if filtered.length === 0 && createCandidate === null}
        <p class="px-2.5 py-2 text-sm text-muted-foreground">No values yet.</p>
      {/if}
    </Combobox.Content>
  </Combobox.Portal>
</Combobox.Root>
