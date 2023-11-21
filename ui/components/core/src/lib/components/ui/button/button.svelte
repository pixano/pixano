<script lang="ts">
  import { Button as ButtonPrimitive } from "bits-ui";
  import { SvelteComponentTyped } from "svelte";
  import { cn } from "../../../utils";
  import { buttonVariants, type Props } from ".";
  // import { buttonVariants, type Props, type Events } from ".";

  type $$Props = Props;
  //   type $$Events = Events;

  let className: $$Props["class"] = undefined;
  export let variant: $$Props["variant"] = "default";
  export let size: $$Props["size"] = "default";
  export let builders: $$Props["builders"] = [];
  export { className as class };

  //   class Button extends SvelteComponentTyped<{ /* your prop definitions */ }> {}
</script>

<div>
  <ButtonPrimitive.Root
    {builders}
    class={cn(buttonVariants({ variant, size, className }))}
    type="button"
    {...$$restProps}
    on:click
    on:keydown
  >
    <slot />
  </ButtonPrimitive.Root>
</div>
