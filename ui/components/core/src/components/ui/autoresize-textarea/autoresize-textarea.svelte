<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { tick } from "svelte";

  export let placeholder: string;
  export let value: string;

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
  class="p-2 border rounded-lg border-gray-200 outline-none text-slate-800 focus:border-primary resize-none overflow-hidden"
  bind:this={textarea}
  bind:value
  on:blur
/>
