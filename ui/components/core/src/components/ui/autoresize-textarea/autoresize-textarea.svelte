<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  export let placeholder: string;
  export let value: string;

  let textarea: HTMLTextAreaElement | null = null;

  $: value !== undefined && resizeTextarea();

  const resizeTextarea = () => {
    if (textarea) {
      textarea.style.height = "auto";
      textarea.style.height = textarea.scrollHeight + "px";
    }
  };
</script>

<textarea
  {placeholder}
  class="p-2 border rounded-lg border-gray-200 outline-none text-slate-800 focus:border-primary resize-none overflow-hidden"
  bind:this={textarea}
  bind:value
  {...$$restProps}
/>
