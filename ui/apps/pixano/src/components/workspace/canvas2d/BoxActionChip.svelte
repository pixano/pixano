<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // The small chip attached to the hovered or edited box: a pencil that toggles edit
  // mode, and a "…" menu with the box's contextual actions. It never takes keyboard
  // focus, so the canvas and video shortcuts keep working while it is used.
  import { Popover } from "bits-ui";
  import { DotsThree, Pencil } from "phosphor-svelte";
  import { onDestroy } from "svelte";

  import type { BoxAction } from "$lib/types/boxActions";
  import { cn, IconButton } from "$lib/ui";

  interface Props {
    open: boolean;
    /** Anything with a client rect; the chip sits above its top-right corner. */
    anchor: { getBoundingClientRect(): DOMRect };
    boundary?: HTMLElement | null;
    editing: boolean;
    editTooltip: string;
    actions: BoxAction[];
    menuOpen: boolean;
    onToggleEdit: () => void;
    onMenuOpenChange: (open: boolean) => void;
    onPointerEnter: () => void;
    onPointerLeave: () => void;
  }

  let {
    open,
    anchor,
    boundary = null,
    editing,
    editTooltip,
    actions,
    menuOpen,
    onToggleEdit,
    onMenuOpenChange,
    onPointerEnter,
    onPointerLeave,
  }: Props = $props();

  const CONFIRM_TIMEOUT_MS = 3000;
  let confirmingId = $state<string | null>(null);
  let confirmTimer: ReturnType<typeof setTimeout> | null = null;
  let contentElement = $state<HTMLElement | null>(null);

  function clearConfirm() {
    if (confirmTimer) clearTimeout(confirmTimer);
    confirmTimer = null;
    confirmingId = null;
  }

  function runAction(action: BoxAction) {
    if (action.disabled) return;
    if (action.destructive && confirmingId !== action.id) {
      clearConfirm();
      confirmingId = action.id;
      confirmTimer = setTimeout(clearConfirm, CONFIRM_TIMEOUT_MS);
      return;
    }
    clearConfirm();
    onMenuOpenChange(false);
    action.run();
  }

  // Close the menu on a press anywhere outside the chip.
  $effect(() => {
    if (!menuOpen) {
      clearConfirm();
      return;
    }
    const onWindowPointerDown = (event: PointerEvent) => {
      if (contentElement && event.target instanceof Node && contentElement.contains(event.target))
        return;
      onMenuOpenChange(false);
    };
    window.addEventListener("pointerdown", onWindowPointerDown, true);
    return () => window.removeEventListener("pointerdown", onWindowPointerDown, true);
  });

  // The content can unmount under the pointer, which then never fires pointerleave.
  $effect(() => {
    if (!open) onPointerLeave();
  });
  onDestroy(() => {
    clearConfirm();
    onPointerLeave();
  });
</script>

<Popover.Root {open}>
  <Popover.Portal>
    <Popover.Content
      bind:ref={contentElement}
      customAnchor={anchor}
      side="top"
      align="end"
      sideOffset={8}
      collisionBoundary={boundary ?? undefined}
      collisionPadding={4}
      strategy="fixed"
      updatePositionStrategy="always"
      hideWhenDetached
      trapFocus={false}
      preventScroll={false}
      interactOutsideBehavior="defer-otherwise-ignore"
      escapeKeydownBehavior="defer-otherwise-ignore"
      onOpenAutoFocus={(event) => event.preventDefault()}
      onCloseAutoFocus={(event) => event.preventDefault()}
      onmousedown={(event) => event.preventDefault()}
      onpointerenter={onPointerEnter}
      onpointerleave={onPointerLeave}
      aria-label="Box actions"
      class="z-40 flex flex-col-reverse gap-0.5 rounded-lg border border-border/50 bg-popover/95 p-0.5 text-popover-foreground shadow-elevation-2 backdrop-blur-md data-[side=bottom]:flex-col"
    >
      <div class="flex items-center justify-end gap-0.5">
        <IconButton
          tooltipContent={editTooltip}
          selected={editing}
          onclick={onToggleEdit}
          class="h-7 w-7 rounded-md"
        >
          <Pencil class="h-3.5 w-3.5" />
        </IconButton>
        {#if actions.length > 0}
          <IconButton
            tooltipContent="More actions"
            selected={menuOpen}
            onclick={() => onMenuOpenChange(!menuOpen)}
            class="h-7 w-7 rounded-md"
          >
            <DotsThree weight="bold" class="h-3.5 w-3.5" />
          </IconButton>
        {/if}
      </div>
      {#if menuOpen && actions.length > 0}
        <div role="menu" class="flex min-w-40 flex-col gap-0.5 border-border/40 p-0.5">
          {#each actions as action (action.id)}
            {@const confirming = confirmingId === action.id}
            <button
              type="button"
              role="menuitem"
              tabindex={-1}
              disabled={action.disabled}
              title={action.disabled ? action.disabledReason : undefined}
              class={cn(
                "flex w-full items-center rounded-md px-2 py-1 text-left text-xs transition-colors disabled:pointer-events-none disabled:opacity-50",
                action.destructive
                  ? "text-destructive hover:bg-destructive/10"
                  : "text-foreground hover:bg-accent",
                confirming && "bg-destructive text-destructive-foreground hover:bg-destructive/90",
              )}
              onclick={() => runAction(action)}
            >
              {confirming ? (action.confirmLabel ?? `Click again: ${action.label}`) : action.label}
            </button>
          {/each}
        </div>
      {/if}
    </Popover.Content>
  </Popover.Portal>
</Popover.Root>
