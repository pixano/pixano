<script lang="ts">
  import { Checkbox as CheckboxPrimitive } from "bits-ui";
  import { Check, Minus } from "lucide-svelte";
  import { cn } from "../../../utils";

  type $$Props = CheckboxPrimitive.Props & { handleClick?: (checked: boolean) => void };
  type $$Events = CheckboxPrimitive.Events & {
    keydown: KeyboardEvent & { detail: { originalEvent: KeyboardEvent } };
  };

  let className: $$Props["class"] = undefined;
  export let disabled: $$Props["disabled"] = false;
  export let checked: $$Props["checked"] = false;
  export { className as class };

  export let handleClick: (checked: $$Props["checked"]) => void;
</script>

<CheckboxPrimitive.Root
  class={cn(
    "box-content peer h-4 w-4 shrink-0 rounded-sm border border-primary ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 data-[state=checked]:bg-primary-light data-[state=checked]:text-primary-foreground data-[disabled=true]:cursor-not-allowed data-[disabled=true]:opacity-50",
    className,
  )}
  bind:checked
  {...$$restProps}
  {disabled}
  on:click={() => handleClick(!checked)}
  on:keydown={(event) => {
    if (event.detail.originalEvent.key === "Enter") {
      handleClick(!checked);
      checked = !checked;
    }
  }}
>
  <CheckboxPrimitive.Indicator
    class={cn("flex items-center justify-center text-current h-4 w-4")}
    let:isChecked
    let:isIndeterminate
  >
    {#if isChecked}
      <Check class="h-3.5 w-3.5" />
    {:else if isIndeterminate}
      <Minus class="h-3.5 w-3.5" />
    {/if}
  </CheckboxPrimitive.Indicator>
</CheckboxPrimitive.Root>
