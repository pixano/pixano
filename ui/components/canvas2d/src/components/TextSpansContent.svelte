<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { onMount } from "svelte";

  import { BaseSchema, TextSpan, type Annotation } from "@pixano/core";
  import { DISPLAY_MENTION_FEATURES } from "@pixano/dataset-item-workspace/src/lib/settings/defaultFeatures";

  export let annotations: Annotation[] | undefined;

  let col_names: string[] = [];
  let mentionRows: { [key: string]: string | undefined }[] = [];

  onMount(() => {
    const textSpans =
      (annotations?.filter((ann) => ann.is_type(BaseSchema.TextSpan)) as TextSpan[]) ?? [];
    // get used fields
    const foundFields = new Set<string>();
    for (const tspan of textSpans) {
      for (const field of DISPLAY_MENTION_FEATURES) {
        const val = tspan.data[field];
        if (typeof val === "string") {
          foundFields.add(field);
        }
      }
    }
    // force "mention"
    foundFields.add("mention");
    // filter col_names
    col_names = DISPLAY_MENTION_FEATURES.filter((f) => foundFields.has(f));
    // build rows
    const rawRows = textSpans.map((tspan) => {
      const row: { [key: string]: string | undefined } = {};
      for (const field of col_names) {
        const val = tspan.data[field];
        row[field] = typeof val === "string" ? val : undefined;
      }
      return row;
    });
    // deduplicate
    const seen = new Set<string>();
    mentionRows = rawRows.filter((row) => {
      const key = JSON.stringify(row);
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });
  });
</script>

{#if mentionRows.length > 0}
  <div class="mt-4 mr-4">
    <p class="font-medium mb-2">Text spans</p>

    <table class="table-auto border-collapse w-full text-sm">
      <thead class="bg-gray-100">
        <tr>
          {#each col_names as col}
            <th class="border px-2 py-1 text-left">{col}</th>
          {/each}
        </tr>
      </thead>
      <tbody>
        {#each mentionRows as row}
          <tr>
            {#each col_names as col}
              <td class="border px-2 py-1">{row[col] ?? ""}</td>
            {/each}
          </tr>
        {/each}
      </tbody>
    </table>
  </div>
{/if}
