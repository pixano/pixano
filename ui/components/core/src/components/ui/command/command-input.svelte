<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { Command as CommandPrimitive } from "cmdk-sv";
  import { Search } from "lucide-svelte";

  import { cn } from "../../../lib/utils/styleUtils";

  type $$Props = CommandPrimitive.InputProps;

  let className: string | undefined | null = undefined;
  export let value: string = "";
  export { className as class };
</script>

<div class="flex items-center border-b px-2" data-cmdk-input-wrapper="">
  <Search class="mr-2 h-4 w-4 shrink-0 opacity-50" />
  <CommandPrimitive.Input
    bind:value
    on:input
    on:focus
    on:blur
    class={cn(
      "flex h-11 w-full rounded-md bg-transparent py-3 text-sm outline-none placeholder:text-muted-foreground disabled:cursor-not-allowed disabled:opacity-50",
      className,
    )}
    {...$$restProps}
  />
</div>
