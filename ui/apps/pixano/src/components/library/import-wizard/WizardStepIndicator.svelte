<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  interface Props {
    steps: string[];
    current: number; // index into steps
  }

  let { steps, current }: Props = $props();
</script>

<div class="flex items-center gap-2 px-6 pb-3 sm:px-7" aria-label="Wizard progress">
  {#each steps as step, index (step)}
    {#if index > 0}
      <div class={`h-px flex-1 ${index <= current ? "bg-primary/50" : "bg-border"}`}></div>
    {/if}
    <div class="flex items-center gap-1.5">
      <span
        class={`flex h-4 w-4 items-center justify-center rounded-full text-[9px] font-semibold ${
          index < current
            ? "bg-primary text-primary-foreground"
            : index === current
              ? "border border-primary text-primary"
              : "border border-border text-muted-foreground"
        }`}
      >
        {index + 1}
      </span>
      <span
        class={`text-[10px] font-medium uppercase tracking-widest ${
          index === current ? "text-foreground" : "text-muted-foreground"
        }`}
      >
        {step}
      </span>
    </div>
  {/each}
</div>
