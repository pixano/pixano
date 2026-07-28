<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { Warning, WarningCircle } from "phosphor-svelte";

  import type { LayoutPreflight } from "./layoutPreflight";

  interface Props {
    layout: LayoutPreflight;
  }

  let { layout }: Props = $props();

  const errors = $derived(layout.findings.filter((finding) => finding.severity === "error"));
  const warnings = $derived(layout.findings.filter((finding) => finding.severity === "warning"));
</script>

<div class="space-y-2 rounded-xl border border-border bg-card p-4">
  <p class="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
    Detected layout
  </p>

  {#if layout.ok}
    <div class="flex flex-wrap items-center gap-1.5 text-xs">
      <span class="font-medium text-foreground">
        {#if layout.encoding === "folders"}
          {layout.totalRecords} video{layout.totalRecords === 1 ? "" : "s"} · {layout.keptFiles} frame{layout.keptFiles ===
          1
            ? ""
            : "s"}
        {:else}
          {layout.totalRecords} record{layout.totalRecords === 1 ? "" : "s"}
        {/if}
      </span>
      {#each layout.views as view (view.name)}
        <span
          class="rounded-full border border-border px-2 py-0.5 font-mono text-[10px] text-muted-foreground"
        >
          {#if layout.encoding === "folders"}
            {view.name} · {view.groupCount ?? 0} video{(view.groupCount ?? 0) === 1 ? "" : "s"} · {view.fileCount}
            frame{view.fileCount === 1 ? "" : "s"}
          {:else}
            {view.name} · {view.kind} · {view.fileCount} file{view.fileCount === 1 ? "" : "s"}
          {/if}
        </span>
      {/each}
      {#if layout.splits.length > 1}
        {#each layout.splits as split (split.name)}
          <span
            class="rounded-full border border-primary/30 px-2 py-0.5 text-[10px] text-muted-foreground"
          >
            {split.name}: {split.recordCount}
          </span>
        {/each}
      {/if}
      {#if layout.ignoredFiles > 0}
        <span class="text-[10px] text-muted-foreground/70">
          ({layout.ignoredFiles} non-matching file{layout.ignoredFiles === 1 ? "" : "s"} skipped)
        </span>
      {/if}
    </div>
  {/if}

  {#each errors as finding (finding.code + finding.message)}
    <p class="flex items-start gap-1.5 text-xs text-destructive">
      <WarningCircle weight="fill" class="mt-0.5 h-3.5 w-3.5 shrink-0" />
      {finding.message}
    </p>
  {/each}
  {#each warnings as finding (finding.code + finding.message)}
    <p class="flex items-start gap-1.5 text-xs text-amber-600 dark:text-amber-400">
      <Warning weight="fill" class="mt-0.5 h-3.5 w-3.5 shrink-0" />
      {finding.message}
    </p>
  {/each}
</div>
