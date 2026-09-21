<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import type { FeatureValues } from "$lib/types/shapeTypes";
  import { Input } from "$lib/ui";
  import {
    parseCollectionValue,
    type ScalarFeatureType,
  } from "$lib/utils/featureValidationSchemas";

  interface Props {
    value?: unknown;
    itemType: ScalarFeatureType;
    label: string;
    required?: boolean;
    onValueChange?: (value: FeatureValues) => void;
    onCommit?: (value: Array<string | number | boolean>) => void;
  }

  let { value, itemType, label, required = false, onValueChange, onCommit }: Props = $props();
  let text = $state("");
  $effect(() => {
    text = typeof value === "string" ? value : JSON.stringify(value ?? []);
  });
  const parsed = $derived(parseCollectionValue(text, itemType));
  const error = $derived(
    parsed.error ||
      (required && "value" in parsed && parsed.value.length === 0 ? `${label} is required.` : ""),
  );
  const example = $derived(
    itemType === "str" ? '["red", "blue"]' : itemType === "bool" ? "[true, false]" : "[1, 2]",
  );

  function change(event: Event) {
    text = (event.currentTarget as HTMLInputElement).value;
    const result = parseCollectionValue(text, itemType);
    onValueChange?.("value" in result ? result.value : text);
  }

  function commit() {
    if (!error && "value" in parsed) onCommit?.(parsed.value);
  }
</script>

<div class="min-w-0 space-y-1">
  <Input
    value={text}
    aria-label={label}
    aria-invalid={!!error}
    oninput={change}
    onchange={commit}
  />
  <p class="text-[10px] text-muted-foreground">List, e.g. {example}</p>
  {#if error}
    <p class="text-xs text-destructive" role="alert">{error}</p>
  {/if}
</div>
