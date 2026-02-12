<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { tick } from "svelte";

  export let placeholder: string;
  export let value: string;
  export let disabled = false;

  let textarea: HTMLTextAreaElement | null = null;

  // We have to include value to trigger the resize
  /* eslint-disable @typescript-eslint/no-unused-expressions */
  $: value !== undefined && void resizeTextarea();

  const resizeTextarea = async () => {
    await tick();
    if (textarea) {
      textarea.style.height = "auto";
      await tick();
      textarea.style.height = textarea.scrollHeight + "px";
    }
  };
</script>

<textarea
  {placeholder}
  {disabled}
  class="p-2 border rounded-lg border-border outline-none text-foreground focus:border-primary resize-none overflow-hidden {$$props.class}"
  bind:this={textarea}
  bind:value
  on:blur
  on:keydown
/>
