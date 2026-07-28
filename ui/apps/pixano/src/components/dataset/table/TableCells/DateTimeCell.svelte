<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  interface Props {
    // Exports
    value: string;
  }

  let { value }: Props = $props();

  const formatted = $derived.by(() => {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "—";
    // Browser locale, compact: "Jul 25, 2026, 6:15 PM" / "25 juil. 2026, 18:15".
    return date.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
  });
</script>

<div class="min-w-24 px-2 whitespace-nowrap text-muted-foreground tabular-nums">
  {formatted}
</div>
