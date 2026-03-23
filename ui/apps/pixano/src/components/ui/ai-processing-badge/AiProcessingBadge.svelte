<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { CircleNotch, WarningCircle } from "phosphor-svelte";

  interface Props {
    message?: string;
    overlay?: boolean;
    variant?: "default" | "error";
  }

  let { message = "Processing...", overlay = false, variant = "default" }: Props = $props();
</script>

{#if overlay}
  <div
    class="fixed inset-0 z-50 flex items-center justify-center bg-black/30 backdrop-blur-[2px]"
    role="status"
    aria-live="polite"
  >
    <div
      class="inline-flex items-center gap-2.5 rounded-xl border px-4 py-2.5 text-sm shadow-[0_4px_24px_rgba(0,0,0,0.12)] backdrop-blur-md
        {variant === 'error'
        ? 'border-destructive/30 bg-card/95 text-foreground'
        : 'border-border/40 bg-card/90 text-foreground'}"
    >
      {#if variant === "error"}
        <WarningCircle weight="regular" class="h-5 w-5 shrink-0 text-destructive" />
      {:else}
        <CircleNotch weight="regular" class="h-5 w-5 shrink-0 animate-spin text-primary" />
      {/if}
      <span class="font-medium">{message}</span>
    </div>
  </div>
{:else}
  <div
    class="inline-flex items-center gap-2.5 rounded-xl border px-4 py-2.5 text-sm shadow-[0_4px_24px_rgba(0,0,0,0.08)] backdrop-blur-sm
      {variant === 'error'
      ? 'border-destructive/30 bg-card/95 text-foreground'
      : 'border-border/40 bg-card/90 text-foreground'}"
    role={variant === "error" ? "alert" : "status"}
    aria-live="polite"
  >
    {#if variant === "error"}
      <WarningCircle weight="regular" class="h-5 w-5 shrink-0 text-destructive" />
    {:else}
      <CircleNotch weight="regular" class="h-5 w-5 shrink-0 animate-spin text-primary" />
    {/if}
    <span class="font-medium">{message}</span>
  </div>
{/if}
