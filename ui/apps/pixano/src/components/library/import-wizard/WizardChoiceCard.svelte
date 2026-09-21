<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { Check, type Images } from "phosphor-svelte";

  import { WIZARD_CHOICE_CARD_CLASS } from "./wizardStyles";

  interface Props {
    icon: typeof Images;
    title: string;
    description: string;
    selected: boolean;
    disabled?: boolean;
    onclick: () => void;
  }

  let { icon: Icon, title, description, selected, disabled = false, onclick }: Props = $props();
</script>

<button
  type="button"
  class={`${WIZARD_CHOICE_CARD_CLASS} flex min-h-20 w-full items-start gap-3 p-3 ${selected ? "border-primary/50 bg-primary/5" : "border-border bg-card hover:border-primary/30 hover:bg-accent/40"}`}
  aria-pressed={selected}
  title={disabled ? "Unavailable on this server" : undefined}
  {disabled}
  {onclick}
>
  <Icon
    size={24}
    weight="regular"
    class={`mt-0.5 shrink-0 ${selected ? "text-primary" : "text-muted-foreground"}`}
    aria-hidden="true"
  />
  <span class="min-w-0 flex-1">
    <span class="block pr-3 text-sm font-medium leading-5 text-foreground">{title}</span>
    <span class="mt-0.5 block text-xs leading-4 text-muted-foreground">{description}</span>
  </span>
  {#if selected}
    <Check
      size={14}
      weight="bold"
      class="absolute right-2.5 top-3.5 text-primary"
      aria-hidden="true"
    />
  {/if}
</button>
