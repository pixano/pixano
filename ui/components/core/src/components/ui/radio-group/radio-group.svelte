<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { Label, RadioGroup } from "bits-ui";
  import { Check } from "lucide-svelte";

  import { cn } from "../../../lib/utils/styleUtils";

  export let selectedValue: string;
  export let values: { value: string; label: string }[];
  export let itemClass: string | undefined = undefined;
</script>

<RadioGroup.Root class="flex flex-col gap-4 text-sm font-medium" bind:value={selectedValue}>
  {#each values as { label, value }}
    <div
      class={cn("group flex select-none items-center text-foreground transition-all", itemClass)}
    >
      <RadioGroup.Item
        id={value}
        {value}
        class="size-5 shrink-0 rounded-full border border-primary transition-all duration-100 ease-in-out data-[state=checked]:bg-primary data-[state=checked]:text-primary-foreground flex items-center justify-center"
      >
        {#if selectedValue === value}
          <Check class="h-3.5 w-3.5" strokeWidth={3} />
        {/if}
      </RadioGroup.Item>

      <Label.Root for={value} class="pl-3">{label}</Label.Root>
    </div>
  {/each}
</RadioGroup.Root>
