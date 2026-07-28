<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import SchemaPanel from "$components/dataset/SchemaPanel.svelte";
  import { CircleNotch, Warning, WarningCircle } from "phosphor-svelte";

  import { formatBytes, groupFindings, sampleLocation } from "./wizardUtils";
  import type { ImportPlanResponse } from "$lib/api/restTypes";

  interface Props {
    analyzing: boolean;
    analyzeError: string;
    plan: ImportPlanResponse | null;
    /** Raw video "reference clips" mode: imports succeed but clips don't play in-app yet. */
    referenceMode?: boolean;
  }

  let { analyzing, analyzeError, plan, referenceMode = false }: Props = $props();

  const grouped = $derived(plan ? groupFindings(plan) : { errors: [], warnings: [] });
  const splitEntries = $derived(Object.entries(plan?.splits ?? {}));
  const totalRecords = $derived(plan?.totals?.records ?? null);
  const mediaEstimate = $derived(formatBytes(plan?.totals?.media_bytes));
  const extractEstimate = $derived(formatBytes(plan?.media_size_estimate_bytes));
  const previewRows = $derived((plan?.previews ?? []).slice(0, 3));
</script>

<div class="px-6 sm:px-7 pb-2 space-y-4">
  {#if analyzing}
    <div class="flex items-center gap-2 py-8 text-sm text-muted-foreground">
      <CircleNotch weight="regular" class="h-4 w-4 animate-spin" />
      Analyzing the source (no data is written)…
    </div>
  {:else if analyzeError}
    <div class="rounded-xl border border-destructive/40 bg-destructive/5 p-4">
      <p class="flex items-center gap-2 text-sm font-medium text-destructive">
        <WarningCircle weight="fill" class="h-4 w-4 shrink-0" />
        Analysis failed
      </p>
      <p class="mt-1 whitespace-pre-wrap text-xs text-foreground/80">{analyzeError}</p>
    </div>
  {:else if plan}
    <div class="rounded-xl border border-border bg-card p-4">
      <div class="flex flex-wrap items-baseline gap-x-6 gap-y-1">
        <p class="text-sm text-foreground">
          <span class="text-lg font-semibold">{totalRecords ?? "?"}</span>
          record{totalRecords === 1 ? "" : "s"}
          {#if plan.totals?.estimated}<span class="text-xs text-muted-foreground">
              (estimated)
            </span>{/if}
        </p>
        {#if mediaEstimate}
          <p class="text-sm text-muted-foreground">~{mediaEstimate} of media</p>
        {/if}
        {#if extractEstimate}
          <p class="text-sm text-muted-foreground">~{extractEstimate} after frame extraction</p>
        {/if}
        <p class="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
          {plan.format}
        </p>
      </div>
      {#if splitEntries.length > 1}
        <div class="mt-2 flex flex-wrap gap-1.5">
          {#each splitEntries as [split, count] (split)}
            <span
              class="rounded-full border border-border px-2 py-0.5 text-[10px] text-muted-foreground"
            >
              {split}: {count ?? "?"}
            </span>
          {/each}
        </div>
      {/if}
    </div>

    {#if plan.inferred_schema}
      <SchemaPanel schema={plan.inferred_schema} />
    {/if}

    {#if referenceMode}
      <div class="rounded-xl border border-amber-500/40 bg-amber-500/5 p-3">
        <p class="flex items-center gap-2 text-xs font-semibold text-amber-600 dark:text-amber-400">
          <Warning weight="fill" class="h-4 w-4 shrink-0" />
          Reference clips will not play in the explorer in this release
        </p>
        <p class="mt-1 text-xs text-foreground/80">
          The videos import as metadata + file references. To annotate or browse frames, go back and
          choose “Extract frames” instead.
        </p>
      </div>
    {/if}

    {#each grouped.errors as finding (finding.code)}
      <div class="rounded-xl border border-destructive/40 bg-destructive/5 p-3">
        <p class="flex items-center gap-2 text-xs font-semibold text-destructive">
          <WarningCircle weight="fill" class="h-4 w-4 shrink-0" />
          {finding.code} · {finding.count} occurrence{finding.count === 1 ? "" : "s"}
        </p>
        {#if finding.suggestion}
          <p class="mt-1 text-xs text-foreground/80">{finding.suggestion}</p>
        {/if}
        {#if finding.samples.length}
          <p class="mt-1 font-mono text-[10px] text-muted-foreground">
            e.g. {finding.samples.slice(0, 2).map(sampleLocation).filter(Boolean).join(", ")}
          </p>
        {/if}
      </div>
    {/each}

    {#each grouped.warnings as finding (finding.code)}
      <div class="rounded-xl border border-amber-500/40 bg-amber-500/5 p-3">
        <p class="flex items-center gap-2 text-xs font-semibold text-amber-600 dark:text-amber-400">
          <Warning weight="fill" class="h-4 w-4 shrink-0" />
          {finding.code} · {finding.count} occurrence{finding.count === 1 ? "" : "s"}
        </p>
        {#if finding.suggestion}
          <p class="mt-1 text-xs text-foreground/80">{finding.suggestion}</p>
        {/if}
      </div>
    {/each}

    {#if previewRows.length}
      <div class="space-y-1.5">
        <p class="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
          Sample records
        </p>
        <div class="max-h-48 space-y-1.5 overflow-y-auto">
          {#each previewRows as preview, index (index)}
            <div class="rounded-lg border border-border bg-card px-3 py-2">
              {#if Object.keys(preview.thumbnails ?? {}).length}
                <div class="mb-1.5 flex gap-1.5">
                  {#each Object.entries(preview.thumbnails) as [view, url] (view)}
                    <img
                      src={url}
                      alt={view}
                      title={view}
                      class="h-12 w-12 rounded-md border border-border object-cover"
                    />
                  {/each}
                </div>
              {/if}
              <div class="font-mono text-[11px] text-muted-foreground">
                {#each Object.entries(preview.record).slice(0, 6) as [key, value] (key)}
                  <span class="mr-3 inline-block">
                    <span class="text-foreground/70">{key}</span>
                    =
                    <span>{JSON.stringify(value)}</span>
                  </span>
                {/each}
              </div>
            </div>
          {/each}
        </div>
      </div>
    {/if}
  {/if}
</div>
