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

<div class="flex items-center gap-3" aria-label="Wizard progress">
  {#each steps as step, index (step)}
    {#if index > 0}
      <div class={`h-px w-8 ${index <= current ? "bg-primary/50" : "bg-border"}`}></div>
    {/if}
    <div class="flex items-center gap-2" aria-current={index === current ? "step" : undefined}>
      <span
        class={`flex h-6 w-6 items-center justify-center rounded-full text-xs font-semibold ${
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
        class={`text-sm font-medium ${
          index === current ? "text-foreground" : "text-muted-foreground"
        }`}
      >
        {step}
      </span>
    </div>
  {/each}
</div>
