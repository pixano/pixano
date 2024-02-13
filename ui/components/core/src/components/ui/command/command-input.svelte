<script lang="ts">
  import { Command as CommandPrimitive } from "cmdk-sv";
  import { Search } from "lucide-svelte";
  import { cn } from "../../../lib/utils/styleUtils";

  type $$Props = CommandPrimitive.InputProps & {
    value: string;
    onValidation: (value: string) => void | null;
  };

  let className: string | undefined | null = undefined;
  export { className as class };
  export let value: string;
  export let onValidation: (value: string) => void | null;

  const onBlur = () => {
    onValidation(value);
  };
</script>

<div class="flex items-center border-b px-2" data-cmdk-input-wrapper="">
  <Search class="mr-2 h-4 w-4 shrink-0 opacity-50" />
  <CommandPrimitive.Input
    on:focus
    on:blur={onBlur}
    class={cn(
      "flex h-11 w-full rounded-md bg-transparent py-3 text-sm outline-none placeholder:text-muted-foreground disabled:cursor-not-allowed disabled:opacity-50",
      className,
    )}
    {...$$restProps}
  />
</div>
