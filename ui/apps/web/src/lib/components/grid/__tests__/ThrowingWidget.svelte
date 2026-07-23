<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  interface Props {
    widgetId: string;
    // The test passes a mutable flag through options so a boundary reset() can
    // re-create the component against a new value.
    options: { crash: { value: boolean } };
    data?: Record<string, unknown>;
  }

  let { options }: Props = $props();

  // Called from the template so the throw happens during render, where a
  // <svelte:boundary> can catch it; a reset() re-renders and re-reads the flag.
  function assertAlive(): string {
    if (options.crash.value) {
      throw new Error("widget exploded");
    }
    return "alive";
  }
</script>

<span data-testid="widget-alive">{assertAlive()}</span>
