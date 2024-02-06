<script lang="ts">
  import { Tabs as TabsPrimitive } from "bits-ui";
  import { cn } from "../../../lib/utils/styleUtils";

  type $$Props = TabsPrimitive.TriggerProps;

  let className: $$Props["class"] = undefined;
  export let value: $$Props["value"];
  export { className as class };
</script>

<TabsPrimitive.Trigger
  class={cn(
    "inline-flex flex-grow items-center justify-center whitespace-nowrap uppercase font-light text-slate-800 px-3 pt-6 pb-2 ring-offset-background transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 border-transparent border-b-2 data-[state=inactive]:bg-white data-[state=active]:font-bold",
    className,
  )}
  {value}
  {...$$restProps}
  on:click
>
  <slot />
</TabsPrimitive.Trigger>
