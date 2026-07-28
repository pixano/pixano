<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { ImageBroken, Info } from "phosphor-svelte";

  interface Props {
    variant: "error" | "empty";
    title: string;
    message?: string;
    /** Optional retry/action button. */
    actionLabel?: string;
    onAction?: () => void;
  }

  let { variant, title, message = "", actionLabel = "", onAction }: Props = $props();
</script>

<!-- Centered state overlay for canvases: a designed error/empty surface instead of a blank void. -->
<div
  class="absolute inset-0 z-10 flex flex-col items-center justify-center gap-3 bg-canvas/80 p-6 text-center backdrop-blur-sm"
>
  <div
    class="flex h-16 w-16 items-center justify-center rounded-2xl {variant === 'error'
      ? 'bg-destructive/10'
      : 'bg-primary/5'}"
  >
    {#if variant === "error"}
      <ImageBroken weight="thin" size={36} class="text-destructive/70" />
    {:else}
      <Info weight="thin" size={36} class="text-primary/40" />
    {/if}
  </div>
  <div class="space-y-1">
    <h3 class="text-base font-bold text-foreground">{title}</h3>
    {#if message}
      <p class="max-w-sm text-sm text-muted-foreground">{message}</p>
    {/if}
  </div>
  {#if actionLabel && onAction}
    <button
      type="button"
      onclick={onAction}
      class="h-9 rounded-xl bg-primary px-4 text-xs font-bold uppercase tracking-wider text-primary-foreground shadow-sm transition-all hover:bg-primary/90 active:scale-95 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
    >
      {actionLabel}
    </button>
  {/if}
</div>
