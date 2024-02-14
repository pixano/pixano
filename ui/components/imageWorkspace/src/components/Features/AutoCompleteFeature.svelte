<script lang="ts">
  import { Check } from "lucide-svelte";
  import { Command, cn } from "@pixano/core/src";

  export let featureList: { value: string; label: string }[] = [];
  export let placeholder: string = "Select an item";
  export let value: string = "";
  export let onTextInputChange: (value: string) => void;
  export let autofocus: boolean = false;
  export let isFixed: boolean = false;

  let open = false;

  const onSelect = (currentValue: string) => {
    value = currentValue;
    onTextInputChange(value);
    open = false;
  };

  const onInputBlur = () => {
    onTextInputChange(value);
    setTimeout(() => {
      open = false;
    }, 200);
  };
</script>

<Command.Root class="overflow-visible">
  <Command.Input
    {placeholder}
    bind:value
    on:blur={onInputBlur}
    on:focus={() => (open = true)}
    class="h-9"
    {autofocus}
  />
  {#if open}
    <div class={cn({ "fixed mt-8 z-10": isFixed })}>
      <Command.Group
        class={cn("z-10 bg-white top-full w-full max-h-[50vh] overflow-auto overflow-x-hidden", {
          absolute: !isFixed,
        })}
      >
        {#each featureList as feat}
          <Command.Item value={feat.value} {onSelect}>
            <Check class={cn("mr-2 h-4 w-4", value !== feat.value && "text-transparent")} />
            {feat.label}
          </Command.Item>
        {/each}
      </Command.Group>
    </div>
  {/if}
</Command.Root>
