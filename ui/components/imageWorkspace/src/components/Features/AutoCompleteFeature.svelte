<script lang="ts">
  import { Check } from "lucide-svelte";
  import { Command, cn } from "@pixano/core/src";

  export let listItems: { value: string; label: string }[] = [];
  export let placeholder: string = "Select an item";
  export let value: string = "";
  // export let selectedValue: string = "";
  export let saveValue: (value: string) => void = () => {};

  let open = false;
  // let inputStatus: "none" | "blur" | "focus" = "none";
  let shouldClose: "no" | "hasBlurred" | "hasSelected" = "no";

  //   let inputValue: string = "";

  //   $: selectedValue = listItems.find((f) => f.value === value)?.label ?? placeholder;

  //   $: console.log({ value, inputValue, selectedValue, listItems });

  //   $: {
  //     if (value) saveValue(value);
  //   }

  // We want to refocus the trigger button when the user selects
  // an item from the list so users can continue navigating the
  // rest of the form with the keyboard.
  // async function closeAndFocusTrigger(triggerId: string) {
  //   tick()
  //     .then(() => {
  //       open = false;
  //       document.getElementById(triggerId)?.focus();
  //     })
  //     .catch((err) => console.error(err));
  // }

  //   const onValidation = (value: string) => {
  //     console.log("validation", { value });
  //     selectedValue = value;
  //     // open = false;
  //   };

  // $: {
  //   if (shouldClose === "hasBlurred") {
  //     open = false;
  //     shouldClose = "no";
  //   }
  // }

  const onSelect = (currentValue: string) => {
    console.log("onSelect", { currentValue });
    // selectedValue = currentValue;
    value = currentValue;
    open = false;
  };

  // const onInput = () => {
  //   selectedValue = "";
  // };

  const onInputBlur = () => {
    if (!listItems.some((listItem) => listItem.value === value) && value !== "") {
      console.log("blur", { value });
      saveValue(value);
    }
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
  />
  {#if open}
    <Command.Group class="z-10 bg-white absolute top-full w-full">
      {#each listItems as val}
        <Command.Item value={val.value} {onSelect}>
          <Check class={cn("mr-2 h-4 w-4", value !== val.value && "text-transparent")} />
          {val.label}
        </Command.Item>
      {/each}
    </Command.Group>
  {/if}
</Command.Root>
