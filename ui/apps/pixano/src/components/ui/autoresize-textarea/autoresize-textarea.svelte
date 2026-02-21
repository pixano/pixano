<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { tick } from "svelte";
  import type { HTMLTextareaAttributes } from "svelte/elements";
 
  import { cn } from "$lib/utils/styleUtils";

  interface Props extends Omit<HTMLTextareaAttributes, "class" | "value"> {
    class?: string;
    placeholder?: string;
    value?: string;
    disabled?: boolean;
  }

  let {
    class: className = undefined,
    placeholder = "",
    value = $bindable(""),
    disabled = false,
    ...restProps
  }: Props = $props();

  let textarea: HTMLTextAreaElement | null = null;

  const resizeTextarea = async () => {
    await tick();
    if (textarea) {
      textarea.style.height = "auto";
      await tick();
      textarea.style.height = textarea.scrollHeight + "px";
    }
  };

  $effect(() => {
    value;
    void resizeTextarea();
  });
</script>

<textarea
  {placeholder}
  {disabled}
  class={cn(
    "p-2 border rounded-lg border-border outline-none text-foreground focus:border-primary resize-none overflow-hidden",
    className,
  )}
  bind:this={textarea}
  bind:value
  {...restProps}
></textarea>
