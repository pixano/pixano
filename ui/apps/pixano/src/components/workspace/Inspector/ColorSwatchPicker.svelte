<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { Popover } from "bits-ui";
  import { Check } from "phosphor-svelte";

  import { ATTRIBUTE_PALETTE, normalizeHexColor } from "$lib/coloring/colorByPalette";
  import { isLuminanceHigh } from "$lib/utils/coreUtils";
  import { BUTTON_TRIGGER_KEYS, handleMenuKeydown } from "$lib/utils/menuKeys";
  import { cn } from "$lib/utils/styleUtils";

  interface Props {
    color: string;
    /** Accessible name of the swatch, e.g. "Color of car". */
    label: string;
    /** The user chose this color. */
    custom?: boolean;
    onPick: (color: string) => void;
  }

  let { color, label, custom = false, onPick }: Props = $props();

  // A click on a swatch or Enter in the hex field applies a color; Escape closes without one.
  let open = $state(false);
  let draft = $state("");
  const draftColor = $derived(normalizeHexColor(draft));

  function handleOpenChange(next: boolean) {
    if (next) draft = color;
  }

  function apply(next: string | null) {
    if (!next) return;
    if (next !== color) onPick(next);
    open = false;
  }

  function onTriggerKeydown(event: KeyboardEvent) {
    handleMenuKeydown(event, open, () => (open = false), BUTTON_TRIGGER_KEYS);
  }

  function onContentKeydown(event: KeyboardEvent) {
    handleMenuKeydown(event, true, () => (open = false));
  }

  function onDraftKeydown(event: KeyboardEvent) {
    if (event.key !== "Enter") return;
    event.preventDefault();
    apply(draftColor);
  }
</script>

<Popover.Root bind:open onOpenChange={handleOpenChange}>
  <Popover.Trigger
    type="button"
    aria-label={label}
    title={label}
    onkeydown={onTriggerKeydown}
    class={cn(
      "h-4 w-4 shrink-0 cursor-pointer rounded-full ring-1 ring-foreground/50 transition-shadow focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background",
      custom && "ring-2 ring-primary",
    )}
    style={`background-color: ${color}`}
  ></Popover.Trigger>
  <Popover.Portal>
    <Popover.Content
      sideOffset={6}
      align="start"
      onkeydown={onContentKeydown}
      class="z-[130] w-56 space-y-2.5 rounded-2xl border border-border/50 bg-popover/95 p-3 text-popover-foreground shadow-elevation-2 backdrop-blur-md"
    >
      <p class="truncate text-[11px] font-semibold text-muted-foreground">{label}</p>
      <div class="grid grid-cols-7 gap-1.5" role="group" aria-label="Palette">
        {#each ATTRIBUTE_PALETTE as swatch (swatch)}
          <button
            type="button"
            aria-label={swatch}
            aria-pressed={swatch === color}
            title={swatch}
            onclick={() => apply(swatch)}
            class="relative h-5 w-5 rounded-full ring-1 ring-foreground/50 transition-transform hover:scale-110 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
            style={`background-color: ${swatch}`}
          >
            {#if swatch === color}
              <Check
                size={11}
                weight="bold"
                class={cn(
                  "absolute inset-0 m-auto",
                  isLuminanceHigh(swatch) ? "text-black" : "text-white",
                )}
              />
            {/if}
          </button>
        {/each}
      </div>
      <div class="flex items-center gap-2">
        <input
          type="color"
          value={draftColor ?? color}
          oninput={(event) => (draft = event.currentTarget.value)}
          aria-label="More colors"
          title="More colors"
          class="h-7 w-7 shrink-0 cursor-pointer rounded-md border border-border/60 bg-background p-0.5"
        />
        <input
          type="text"
          bind:value={draft}
          onkeydown={onDraftKeydown}
          aria-label="Hex color"
          aria-invalid={!draftColor}
          maxlength={7}
          spellcheck={false}
          placeholder="#rrggbb"
          class={cn(
            "h-7 min-w-0 flex-1 rounded-md border bg-background px-2 font-mono text-xs focus:outline-none focus:ring-1 focus:ring-primary/40",
            draftColor ? "border-border/60" : "border-destructive/60",
          )}
        />
        <button
          type="button"
          disabled={!draftColor || draftColor === color}
          onclick={() => apply(draftColor)}
          class="h-7 shrink-0 rounded-md bg-primary px-2 text-[11px] font-semibold text-primary-foreground transition-colors hover:bg-primary/90 disabled:pointer-events-none disabled:opacity-50"
        >
          Apply
        </button>
      </div>
    </Popover.Content>
  </Popover.Portal>
</Popover.Root>
