<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import type { Snippet } from "svelte";

  import { Button, Tooltip } from "bits-ui";

  import { cn } from "$lib/utils/styleUtils";

  interface Props {
    tooltipContent?: string;
    selected?: boolean;
    disabled?: boolean;
    redconfirm?: boolean;
    big?: boolean;
    class?: string;
    onclick?: (event: MouseEvent) => void;
    children?: Snippet;
  }

  let {
    tooltipContent = "",
    selected = false,
    disabled = false,
    redconfirm = false,
    big = false,
    class: className = undefined,
    onclick,
    children,
  }: Props = $props();

  let redConfirmState = $state(false);
  const buttonBaseClass =
    "inline-flex items-center justify-center rounded-lg text-sm font-medium whitespace-nowrap ring-offset-background transition-colors duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 bg-primary text-primary-foreground hover:bg-primary/90";

  function handleClick(event: MouseEvent) {
    if (redconfirm && !redConfirmState) {
      redConfirmState = true;
      event.stopPropagation();
      setTimeout(() => (redConfirmState = false), 3000);
    } else {
      redConfirmState = false;
      onclick?.(event);
    }
  }
</script>

<Tooltip.Root>
  <Tooltip.Trigger tabindex={-1} class="relative">
    {#if redConfirmState}
      <div
        class="absolute right-full top-1/2 -translate-y-1/2 mr-2 bg-popover text-popover-foreground border border-border text-sm px-3 py-1 rounded shadow-lg whitespace-nowrap z-10"
      >
        Click again to confirm suppression
      </div>
    {/if}
    <Button.Root
      {disabled}
      type="button"
      class={cn(
        buttonBaseClass,
        big ? "h-11 px-8" : "h-10 w-10",
        "bg-accent/10 text-foreground hover:bg-accent transition-all duration-200 relative active:scale-95 rounded-xl",
        {
          "bg-destructive text-destructive-foreground hover:bg-destructive/90": redConfirmState,
          "bg-primary text-primary-foreground shadow-sm": selected,
        },
        className,
      )}
      onclick={handleClick}
    >
      {@render children?.()}
    </Button.Root>
  </Tooltip.Trigger>
  {#if tooltipContent}
    <Tooltip.Content
      class="z-50 overflow-hidden rounded-md border border-border/40 bg-popover/90 backdrop-blur-sm px-3 py-1.5 text-sm text-popover-foreground shadow-glass-sm"
    >
      <p>{tooltipContent}</p>
    </Tooltip.Content>
  {/if}
</Tooltip.Root>
