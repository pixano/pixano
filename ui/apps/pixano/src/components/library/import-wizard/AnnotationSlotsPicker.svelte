<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  interface Props {
    choices: string[];
    selected: string[];
  }

  let { choices, selected = $bindable() }: Props = $props();

  function toggle(slot: string) {
    selected = selected.includes(slot) ? selected.filter((s) => s !== slot) : [...selected, slot];
  }
</script>

<div class="space-y-1.5">
  <p class="text-xs text-muted-foreground">Annotation types you plan to create in Pixano.</p>
  <div class="flex flex-wrap gap-1.5">
    {#each choices as slot (slot)}
      {@const active = selected.includes(slot)}
      <button
        type="button"
        class={`rounded-full border px-2.5 py-1 font-mono text-[11px] transition-colors ${
          active
            ? "border-primary bg-primary/10 text-primary"
            : "border-border text-muted-foreground hover:border-primary/40"
        }`}
        aria-pressed={active}
        onclick={() => toggle(slot)}
      >
        {slot}
      </button>
    {/each}
  </div>
</div>
