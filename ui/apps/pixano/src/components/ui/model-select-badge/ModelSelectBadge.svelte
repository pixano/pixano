<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { Select } from "bits-ui";
  import { CaretDown, Check, Robot } from "phosphor-svelte";

  import {
    formatInferenceProviderName,
    getInferenceModelKey,
    type InferenceModel,
  } from "$lib/types/inference";
  import { cn } from "$lib/utils/styleUtils";

  interface Props {
    models: InferenceModel[];
    selectedModelKey: string;
    disabled?: boolean;
    label?: string;
    onValueChange?: (key: string) => void;
  }

  let { models, selectedModelKey, disabled = false, label, onValueChange }: Props = $props();

  let isOpen = $state(false);

  function shortName(name: string): string {
    const idx = name.lastIndexOf("/");
    return idx >= 0 ? name.substring(idx + 1) : name;
  }

  let displayLabel = $derived(
    shortName(
      label ??
        models.find((m) => getInferenceModelKey(m) === selectedModelKey)?.name ??
        "Select model",
    ),
  );

  let items = $derived(models.map((m) => ({ value: getInferenceModelKey(m), label: m.name })));

  let chipClass = $derived(
    cn(
      "inline-flex h-7 max-w-[12rem] items-center gap-2 rounded-full border px-2.5 text-[11px] font-normal shadow-sm backdrop-blur-sm transition-all duration-200",
      "bg-background/82 text-foreground border-border/45",
      "hover:bg-background/96 hover:border-border/70 hover:shadow-md",
      {
        "border-primary/35 bg-primary/8 shadow-[0_6px_18px_hsl(var(--primary)/0.12)]": isOpen,
        "opacity-55 shadow-none hover:border-border/45 hover:bg-background/82": disabled,
      },
    ),
  );
</script>

<Select.Root
  type="single"
  value={selectedModelKey}
  {items}
  {disabled}
  open={isOpen}
  onOpenChange={(open) => (isOpen = open)}
  onValueChange={(value) => {
    if (value) onValueChange?.(value);
  }}
>
  <Select.Trigger aria-label="Model selection" class={chipClass}>
    {#snippet children()}
      <Robot
        weight="fill"
        class={cn("h-3.5 w-3.5 shrink-0 text-muted-foreground transition-colors", {
          "text-primary": isOpen && !disabled,
        })}
      />
      <span class="min-w-0 flex-1 truncate text-left">
        {displayLabel}
      </span>
      <CaretDown
        class={cn("h-3.5 w-3.5 shrink-0 text-muted-foreground transition-transform duration-200", {
          "rotate-180": isOpen,
        })}
      />
    {/snippet}
  </Select.Trigger>

  {#if models.length > 0}
    <Select.Portal>
      <Select.Content
        sideOffset={10}
        class="z-50 min-w-[15rem] overflow-hidden rounded-2xl border border-border/50 bg-popover/96 p-1.5 text-popover-foreground shadow-[0_18px_48px_rgba(15,23,42,0.18)] backdrop-blur-md"
      >
        {#each models as model}
          {@const modelKey = getInferenceModelKey(model)}
          {@const isSelected = selectedModelKey === modelKey}
          <Select.Item
            value={modelKey}
            label={model.name}
            class="cursor-pointer rounded-xl px-3 py-2 outline-none transition-colors data-[highlighted]:bg-accent/80 data-[highlighted]:text-accent-foreground"
          >
            {#snippet children()}
              <div class="flex items-center gap-3">
                <div
                  class={cn(
                    "flex h-7 w-7 shrink-0 items-center justify-center rounded-full border bg-background/70",
                    isSelected
                      ? "border-primary/25 text-primary"
                      : "border-border/35 text-muted-foreground/70",
                  )}
                >
                  {#if isSelected}
                    <Check class="h-3.5 w-3.5" />
                  {:else}
                    <Robot weight="fill" class="h-3.5 w-3.5" />
                  {/if}
                </div>

                <div class="min-w-0 flex-1">
                  <div
                    class={cn("truncate text-[13px] font-semibold", {
                      "text-foreground": isSelected,
                    })}
                  >
                    {model.name}
                  </div>
                  <div class="truncate text-[11px] text-muted-foreground">
                    {formatInferenceProviderName(model.provider_name)}
                  </div>
                </div>

                {#if isSelected}
                  <div
                    class="text-[10px] font-semibold uppercase tracking-[0.12em] text-primary/80"
                  >
                    Active
                  </div>
                {/if}
              </div>
            {/snippet}
          </Select.Item>
        {/each}
      </Select.Content>
    </Select.Portal>
  {/if}
</Select.Root>
