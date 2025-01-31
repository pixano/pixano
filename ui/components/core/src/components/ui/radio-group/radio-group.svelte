<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->
<script lang="ts">
  import { Label, RadioGroup } from "bits-ui";
  import { Check } from "lucide-svelte";

  export let selectedValue: string;
  export let values: { id: string; value: string }[];
</script>

<RadioGroup.Root class="flex flex-col gap-4 text-sm font-medium" bind:value={selectedValue}>
  {#each values as { id, value }}
    <div class="group flex select-none items-center text-foreground transition-all">
      <RadioGroup.Item
        {id}
        {value}
        class="size-5 shrink-0 rounded-full border border-primary transition-all duration-100 ease-in-out data-[state=checked]:bg-primary-light data-[state=checked]:text-primary-foreground flex items-center justify-center"
      >
        {#if selectedValue === value}
          <Check class="h-3.5 w-3.5" />
        {/if}
      </RadioGroup.Item>

      <Label.Root for={id} class="pl-3">{value}</Label.Root>
    </div>
  {/each}
</RadioGroup.Root>
