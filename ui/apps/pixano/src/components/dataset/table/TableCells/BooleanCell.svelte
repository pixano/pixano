<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { Checkbox } from "bits-ui";
  import { Check } from "phosphor-svelte";

  interface Props {
    // Exports
    value: boolean;
  }

  let { value }: Props = $props();
</script>

<div class="flex items-center justify-center px-4">
  <Checkbox.Root
    disabled={true}
    checked={value}
    class="peer h-4 w-4 shrink-0 rounded border border-primary ring-offset-background transition-colors data-[state=checked]:bg-primary data-[state=checked]:text-primary-foreground data-[disabled]:cursor-not-allowed data-[disabled]:opacity-50"
  >
    {#snippet children({ checked })}
      <span class="flex items-center justify-center text-current h-full w-full">
        {#if checked}
          <Check class="h-3.5 w-3.5" />
        {/if}
      </span>
    {/snippet}
  </Checkbox.Root>
</div>
