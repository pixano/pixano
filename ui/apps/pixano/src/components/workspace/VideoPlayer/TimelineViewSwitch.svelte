<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Every camera, or one alone, in the player bar of a multi-camera record: segmented buttons
  // up to three cameras when the bar has room, a menu otherwise. The buttons are plain: the
  // arrow keys stay the frame shortcuts.
  import { Select } from "bits-ui";
  import { CaretDown, Check, VideoCamera } from "phosphor-svelte";

  import { handleMenuKeydown, SELECT_TRIGGER_KEYS } from "$lib/utils/menuKeys";
  import { cn } from "$lib/utils/styleUtils";

  /** Up to this many cameras show as buttons; more go in a menu. */
  const MAX_SEGMENTS = 3;

  interface Props {
    views: readonly string[];
    /** The camera shown alone, or null for all of them. */
    selected: string | null;
    onSelect: (view: string | null) => void;
  }

  let { views, selected, onSelect }: Props = $props();

  let open = $state(false);

  // Options are keyed by position, so no camera name can collide with "All views".
  const options = $derived([
    { value: "0", label: "All views", view: null },
    ...views.map((view, index) => ({ value: String(index + 1), label: view, view })),
  ]);
  const selectedOption = $derived(
    options.find((option) => option.view !== null && option.view === selected) ?? options[0],
  );
</script>

{#snippet menu()}
  <Select.Root
    type="single"
    bind:open
    value={selectedOption.value}
    onValueChange={(next: string) => {
      const option = options.find((candidate) => candidate.value === next);
      if (option) onSelect(option.view);
    }}
  >
    <Select.Trigger
      aria-label={`Timeline cameras: ${selectedOption.label}`}
      title={`Cameras: ${selectedOption.label}`}
      onkeydown={(event: KeyboardEvent) =>
        handleMenuKeydown(event, open, () => (open = false), SELECT_TRIGGER_KEYS)}
      class="inline-flex h-7 min-w-0 max-w-40 items-center gap-1.5 rounded-lg border border-border bg-muted/50 px-2 text-xs text-foreground transition-colors hover:bg-accent/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
    >
      {#snippet children()}
        <VideoCamera class="size-3.5 shrink-0 text-foreground/65" />
        <span class="hidden truncate @3xl:inline">{selectedOption.label}</span>
        <CaretDown size={11} class="shrink-0 text-foreground/65" />
      {/snippet}
    </Select.Trigger>
    <Select.Portal>
      <Select.Content
        sideOffset={6}
        onkeydown={(event: KeyboardEvent) => handleMenuKeydown(event, true, () => (open = false))}
        class="z-[130] max-h-72 min-w-40 overflow-y-auto rounded-2xl border border-border/50 bg-popover/95 p-1.5 text-popover-foreground shadow-elevation-2 backdrop-blur-md"
      >
        {#each options as option (option.value)}
          <Select.Item
            value={option.value}
            label={option.label}
            class="flex cursor-pointer items-center gap-2 rounded-lg px-2 py-1.5 text-xs outline-none transition-colors data-[highlighted]:bg-accent data-[highlighted]:text-accent-foreground"
          >
            <Check
              size={12}
              class={option === selectedOption ? "text-primary" : "text-transparent"}
            />
            <span class="truncate">{option.label}</span>
          </Select.Item>
        {/each}
      </Select.Content>
    </Select.Portal>
  </Select.Root>
{/snippet}

{#if views.length > MAX_SEGMENTS}
  {@render menu()}
{:else}
  <div
    role="group"
    aria-label="Timeline cameras"
    class="hidden h-7 min-w-0 items-center gap-0.5 overflow-x-auto rounded-lg border border-border bg-muted/50 p-0.5 @4xl:flex"
  >
    {#each options as option (option.value)}
      <button
        type="button"
        aria-pressed={option === selectedOption}
        title={option.view === null ? "Show every camera" : `Show ${option.view} alone`}
        class={cn(
          "h-6 max-w-28 shrink-0 truncate rounded-md px-2 text-xs transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring",
          option === selectedOption
            ? "bg-card font-medium text-foreground shadow-sm"
            : "text-foreground/65 hover:text-foreground",
        )}
        onclick={() => onSelect(option.view)}
      >
        {option.label}
      </button>
    {/each}
  </div>
  <div class="min-w-0 @4xl:hidden">
    {@render menu()}
  </div>
{/if}
