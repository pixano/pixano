<script lang="ts">
  import { Check } from "lucide-svelte";
  import { Command, cn } from "@pixano/core/src";

  export let listItems: { value: string; label: string }[] = [];
  export let placeholder: string = "Select an item";
  export let value: string = "";
  export let onTextInputChange: (value: string) => void;
  export let autofocus: boolean = false;

  let open = false;

  const onSelect = (currentValue: string) => {
    value = currentValue;
    open = false;
  };

  const onInputBlur = () => {
    onTextInputChange(value);
    setTimeout(() => {
      open = false;
    }, 200);
  };
</script>

<Command.Root class="overflow-visible" on:blur={() => console.log("blurred")}>
  <Command.Input
    {placeholder}
    bind:value
    on:blur={onInputBlur}
    on:focus={() => (open = true)}
    class="h-9"
    {autofocus}
  />
  {#if open}
    <Command.Group
      class="z-10 bg-white absolute top-full w-full max-h-[50vh] overflow-auto overflow-x-hidden"
    >
      {#each listItems as val}
        <Command.Item value={val.value} {onSelect}>
          <Check class={cn("mr-2 h-4 w-4", value !== val.value && "text-transparent")} />
          {val.label}
        </Command.Item>
      {/each}
    </Command.Group>
  {/if}
</Command.Root>
