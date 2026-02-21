<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import type { Snippet } from "svelte";
  import type { HTMLInputAttributes } from "svelte/elements";

  import { cn } from "$lib/utils/styleUtils";

  interface Props extends Omit<HTMLInputAttributes, "class" | "value" | "autofocus"> {
    class?: string;
    value?: string | number | undefined;
    autofocus?: boolean;
    children?: Snippet;
  }

  let {
    class: className = undefined,
    value = $bindable(undefined),
    autofocus = false,
    children,
    ...restProps
  }: Props = $props();
</script>

<div
  class={cn(
    "flex h-10 items-center rounded-lg border border-input bg-background pl-3 text-sm ring-offset-background focus-within:ring-1 focus-within:ring-primary/30 focus-within:ring-offset-2",
    className,
  )}
>
  {@render children?.()}
  <input
    class={cn(
      "w-full p-2 placeholder:text-muted-foreground focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-50",
      className,
    )}
    bind:value
    {...restProps}
    {...autofocus ? { autofocus: true } : {}}
  />
</div>
