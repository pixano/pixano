<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import type { Snippet } from "svelte";

  import { Button, Tooltip } from "bits-ui";

  import { cn } from "$lib/utils/styleUtils";
  import { buttonVariants } from "$lib/utils/buttonVariants";

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
        buttonVariants({ size: big ? "lg" : "icon" }),
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
