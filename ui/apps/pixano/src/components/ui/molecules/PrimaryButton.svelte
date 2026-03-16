<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { Button } from "bits-ui";
  import type { Snippet } from "svelte";

  import { cn } from "$lib/utils/styleUtils";

  interface Props {
    isSelected?: boolean;
    disabled?: boolean;
    brighter?: boolean;
    class?: string;
    children?: Snippet;
    onclick?: (event: MouseEvent) => void;
  }

  let {
    isSelected = false,
    disabled = false,
    brighter = false,
    class: className = undefined,
    children,
    onclick,
  }: Props = $props();
  const defaultButtonClass =
    "inline-flex items-center justify-center rounded-lg text-sm font-medium whitespace-nowrap ring-offset-background transition-colors duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 bg-primary text-primary-foreground hover:bg-primary/90 h-10 px-4 py-2";
</script>

<Button.Root
  {disabled}
  type="button"
  class={cn(
    defaultButtonClass,
    "font-bold text-xs uppercase tracking-widest h-9 px-5 border rounded-xl transition-all duration-200 flex gap-2 items-center justify-center shadow-sm active:scale-95",
    {
      "bg-primary hover:bg-primary/90 border-primary text-primary-foreground hover:shadow-md":
        isSelected,
      "bg-card border-border text-foreground hover:bg-accent hover:border-border/80": !isSelected,
    },
    className,
  )}
  {onclick}
>
  {@render children?.()}
  {#if brighter}
    <span class="relative flex size-3">
      <span
        class="absolute inline-flex h-full w-full animate-ping rounded-full bg-primary opacity-75"
      ></span>
      <span class="relative inline-flex size-3 rounded-full bg-primary"></span>
    </span>
  {/if}
</Button.Root>
