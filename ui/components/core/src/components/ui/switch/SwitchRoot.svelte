<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { Switch as SwitchPrimitive } from "bits-ui";

  import { cn } from "../../../lib/utils/styleUtils";

  type $$Props = SwitchPrimitive.Props & {
    onChange: (checked: boolean | undefined) => void | null;
  };

  let className: $$Props["class"] = undefined;
  export let checked: $$Props["checked"] = undefined;
  export { className as class };
  export let onChange: (checked: boolean | undefined) => void = () => {};

  $: {
    onChange(checked);
  }
</script>

<SwitchPrimitive.Root
  bind:checked
  class={cn(
    "peer inline-flex h-[24px] w-[44px] shrink-0 cursor-pointer items-center rounded-full border-2 border-transparent transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:cursor-not-allowed disabled:opacity-50 data-[state=checked]:bg-primary data-[state=unchecked]:bg-input",
    className,
  )}
  {...$$restProps}
>
  <SwitchPrimitive.Thumb
    class={cn(
      "pointer-events-none block h-5 w-5 rounded-full bg-background shadow-lg ring-0 transition-transform data-[state=checked]:translate-x-5 data-[state=unchecked]:translate-x-0",
    )}
  />
</SwitchPrimitive.Root>
