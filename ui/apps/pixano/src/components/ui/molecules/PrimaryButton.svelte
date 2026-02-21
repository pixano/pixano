<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import type { Snippet } from "svelte";

  import { Button } from "bits-ui";

  import { cn } from "$lib/utils/styleUtils";
  import { buttonVariants } from "$lib/utils/buttonVariants";

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
</script>

<Button.Root
  {disabled}
  type="button"
  class={cn(
    buttonVariants(),
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
