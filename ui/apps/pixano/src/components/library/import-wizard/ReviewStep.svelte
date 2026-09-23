<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import SchemaPanel from "$components/dataset/SchemaPanel.svelte";
  import { CircleNotch, Warning, WarningCircle } from "phosphor-svelte";

  import { ANNOTATION_TOOLS, ATTR_TYPE_LABELS } from "./rawSchema";
  import { formatBytes, groupFindings, sampleLocation } from "./wizardUtils";
  import type { ImportPlanResponse, SchemaDescriptor } from "$lib/api/restTypes";

  interface Props {
    analyzing: boolean;
    analyzeError: string;
    plan: ImportPlanResponse | null;
    datasetName?: string;
    sourceLabel?: string;
    /** Resolved Video views store references; these clips do not play in-app yet. */
    referenceMode?: boolean;
  }

  let {
    analyzing,
    analyzeError,
    plan,
    datasetName = "",
    sourceLabel = "",
    referenceMode = false,
  }: Props = $props();

  const annotationLabels: Record<string, string> = {
    keypoint: "Keypoints",
    classification: "Classification",
    relation: "Relationships",
    ...Object.fromEntries(
      Object.entries(ANNOTATION_TOOLS).map(([slot, tool]) => [slot, tool.label]),
    ),
  };
  const viewLabels: Record<string, string> = {
    Image: "Images",
    SequenceFrame: "Video frames",
    Video: "Video clips",
    Text: "Text",
    PointCloud: "Point clouds",
  };
  const typeLabels: Record<string, string> = {
    ...ATTR_TYPE_LABELS,
    FixedSizeList: "Vector",
  };
  const formatLabels: Record<string, string> = {
    lerobot: "LeRobot",
    coco: "COCO",
    pixano_jsonl: "Pixano",
  };
  const metadataSlots = new Set([
    "workspace",
    "views",
    "record",
    "entity",
    "entity_dynamic_state",
    "timeseries",
  ]);

  function readableName(value: string): string {
    const words = value.replaceAll("_", " ");
    return words.charAt(0).toUpperCase() + words.slice(1);
  }

  function isDescriptor(value: unknown): value is SchemaDescriptor {
    return value !== null && typeof value === "object" && !Array.isArray(value);
  }

  const grouped = $derived(plan ? groupFindings(plan) : { errors: [], warnings: [] });
  const splitEntries = $derived(Object.entries(plan?.splits ?? {}));
  const totalRecords = $derived(plan?.totals?.records ?? null);
  const mediaEstimate = $derived(formatBytes(plan?.totals?.media_bytes));
  const extractEstimate = $derived(formatBytes(plan?.media_size_estimate_bytes));
  const previewRows = $derived((plan?.previews ?? []).slice(0, 3));
  const recordLabel = $derived(plan?.format === "lerobot" ? "episode" : "record");
  const views = $derived(Object.entries(plan?.inferred_schema?.views ?? {}));
  const annotations = $derived(
    Object.entries(plan?.inferred_schema ?? {})
      .filter(([slot, descriptor]) => !metadataSlots.has(slot) && isDescriptor(descriptor))
      .map(([slot]) => ({ slot, label: annotationLabels[slot] ?? readableName(slot) })),
  );
  const attributeGroups = $derived(
    [
      { title: "Object attributes", descriptor: plan?.inferred_schema?.entity },
      {
        title: plan?.format === "lerobot" ? "Episode attributes" : "Record attributes",
        descriptor: plan?.inferred_schema?.record,
      },
      {
        title: "Per-frame object attributes",
        descriptor: plan?.inferred_schema?.entity_dynamic_state,
      },
    ]
      .map(({ title, descriptor }) => ({
        title,
        fields: Object.entries(descriptor?.fields ?? {}),
      }))
      .filter(({ fields }) => fields.length > 0),
  );
  const hasTimeSeries = $derived(isDescriptor(plan?.inferred_schema?.timeseries));
</script>

<div class="space-y-5 px-6 pb-4 sm:px-7">
  {#if analyzing}
    <div class="flex items-center gap-2 py-8 text-sm text-muted-foreground">
      <CircleNotch weight="regular" class="h-4 w-4 animate-spin" />
      Analyzing source…
    </div>
  {:else if analyzeError}
    <div class="rounded-xl border border-destructive/40 bg-destructive/5 p-4" role="alert">
      <p class="flex items-center gap-2 text-sm font-medium text-destructive">
        <WarningCircle weight="fill" class="h-4 w-4 shrink-0" />
        Analysis failed
      </p>
      <p class="mt-1 whitespace-pre-wrap text-xs text-foreground/80">{analyzeError}</p>
    </div>
  {:else if plan}
    {#if grouped.errors.length}
      <section class="rounded-xl border border-destructive/40 bg-destructive/5 p-4" role="alert">
        <h3 class="flex items-center gap-2 text-sm font-semibold text-destructive">
          <WarningCircle weight="fill" class="h-4 w-4 shrink-0" />
          Validation errors
        </h3>
        <div class="mt-3 space-y-4">
          {#each grouped.errors as finding (finding.code)}
            <div>
              <p class="text-sm font-medium text-foreground">
                {readableName(finding.code)}
                {#if finding.count > 1}
                  <span class="text-xs font-normal text-muted-foreground">
                    · {finding.count} occurrences
                  </span>
                {/if}
              </p>
              {#if finding.suggestion}
                <p class="mt-1 whitespace-pre-wrap break-words text-sm text-foreground/80">
                  {finding.suggestion}
                </p>
              {/if}
              {#if finding.samples.length}
                <p class="mt-1 break-all text-xs text-muted-foreground">
                  {finding.samples.slice(0, 2).map(sampleLocation).filter(Boolean).join(", ")}
                </p>
              {/if}
            </div>
          {/each}
        </div>
      </section>
    {/if}

    <section aria-label="Dataset summary" class="rounded-xl border border-border bg-card p-5">
      <div class="flex flex-wrap items-start justify-between gap-3">
        <div class="min-w-0 space-y-1">
          <h3 class="break-words text-base font-semibold text-foreground">
            {datasetName || "Dataset summary"}
          </h3>
          {#if sourceLabel && sourceLabel !== datasetName}
            <p class="break-words text-sm text-muted-foreground">Source: {sourceLabel}</p>
          {/if}
        </div>
        <span class="rounded-full bg-muted px-2.5 py-1 text-xs font-medium text-muted-foreground">
          {formatLabels[plan.format] ?? readableName(plan.format)}
        </span>
      </div>
      <div class="mt-4 flex flex-wrap items-baseline gap-x-7 gap-y-2">
        <p class="text-sm text-muted-foreground">
          <span class="mr-1 text-2xl font-semibold tabular-nums text-foreground">
            {totalRecords?.toLocaleString() ?? "Unknown"}
          </span>
          {recordLabel}{totalRecords === 1 ? "" : "s"}
          {#if plan.totals?.estimated}<span class="text-xs">(estimated)</span>{/if}
        </p>
        {#if views.length}
          <p class="text-sm text-muted-foreground">
            <span class="mr-1 text-2xl font-semibold tabular-nums text-foreground">
              {views.length}
            </span>
            {plan.format === "lerobot" ? "camera" : "view"}{views.length === 1 ? "" : "s"}
          </p>
        {/if}
      </div>
      {#if mediaEstimate || extractEstimate}
        <p class="mt-3 text-sm text-muted-foreground">
          {#if mediaEstimate}Media: ~{mediaEstimate}{/if}
          {#if mediaEstimate && extractEstimate}<span class="mx-1">·</span>{/if}
          {#if extractEstimate}Extracted frames: ~{extractEstimate}{/if}
        </p>
      {/if}
      {#if splitEntries.length}
        <div class="mt-4 flex flex-wrap gap-2" aria-label="Dataset splits">
          {#each splitEntries as [split, count] (split)}
            <span class="rounded-md border border-border px-2 py-1 text-xs text-muted-foreground">
              {split}: {count?.toLocaleString() ?? "unknown"}
            </span>
          {/each}
        </div>
      {/if}
    </section>

    {#if referenceMode}
      <div class="rounded-xl border border-amber-500/40 bg-amber-500/5 p-3">
        <p class="flex items-center gap-2 text-xs font-semibold text-amber-600 dark:text-amber-400">
          <Warning weight="fill" class="h-4 w-4 shrink-0" />
          Video reference playback is not supported in this release
        </p>
        <p class="mt-1 text-xs text-foreground/80">
          Videos are stored as metadata and file references. Select “Extract frames” in setup to
          annotate or browse frames.
        </p>
      </div>
    {/if}

    {#each grouped.warnings as finding (finding.code)}
      <div class="rounded-xl border border-amber-500/40 bg-amber-500/5 p-3">
        <p class="flex items-center gap-2 text-xs font-semibold text-amber-600 dark:text-amber-400">
          <Warning weight="fill" class="h-4 w-4 shrink-0" />
          {readableName(finding.code)} · {finding.count} occurrence{finding.count === 1 ? "" : "s"}
        </p>
        {#if finding.suggestion}
          <p class="mt-1 whitespace-pre-wrap break-words text-sm text-foreground/80">
            {finding.suggestion}
          </p>
        {/if}
      </div>
    {/each}

    {#if plan.inferred_schema}
      <div class="grid gap-4 md:grid-cols-2">
        <section class="min-w-0 rounded-xl border border-border bg-card p-5">
          <h3 class="text-sm font-semibold text-foreground">Media views</h3>
          {#if views.length}
            <dl class="mt-3 space-y-2.5">
              {#each views as [name, descriptor] (name)}
                <div class="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1 text-sm">
                  <dt class="break-words font-medium text-foreground">{name}</dt>
                  <dd class="text-muted-foreground">
                    {viewLabels[descriptor.base ?? ""] ?? readableName(descriptor.base ?? "View")}
                  </dd>
                </div>
              {/each}
            </dl>
          {:else}
            <p class="mt-3 text-sm text-muted-foreground">No media views.</p>
          {/if}
          {#if hasTimeSeries}
            <p class="mt-4 border-t border-border pt-3 text-sm text-muted-foreground">
              Time-series data included.
            </p>
          {/if}
        </section>

        <section class="min-w-0 rounded-xl border border-border bg-card p-5">
          <h3 class="text-sm font-semibold text-foreground">Annotation setup</h3>
          {#if annotations.length}
            <div class="mt-3 flex flex-wrap gap-2">
              {#each annotations as annotation (annotation.slot)}
                <span
                  class="rounded-md bg-primary/5 px-2.5 py-1.5 text-xs font-medium text-foreground"
                >
                  {annotation.label}
                </span>
              {/each}
            </div>
          {:else}
            <p class="mt-3 text-sm text-muted-foreground">No annotation tools configured.</p>
          {/if}
          {#if !Object.keys(plan.inferred_schema.entity?.fields ?? {}).length}
            <p class="mt-3 text-sm text-muted-foreground">No custom object attributes.</p>
          {/if}
        </section>
      </div>

      {#if attributeGroups.length}
        <section aria-label="Attribute summary" class="rounded-xl border border-border bg-card p-5">
          <div class="space-y-4">
            {#each attributeGroups as group (group.title)}
              <div>
                <h3 class="text-sm font-semibold text-foreground">{group.title}</h3>
                <div class="mt-2 flex flex-wrap gap-2">
                  {#each group.fields as [name, field] (name)}
                    <div class="rounded-lg border border-border px-3 py-2 text-sm">
                      <span class="break-all font-medium text-foreground">{name}</span>
                      <span class="ml-1.5 text-xs text-muted-foreground">
                        {typeLabels[field.type ?? ""] ?? readableName(field.type ?? "Value")}
                        {field.collection ? " list" : ""}{field.required ? " · required" : ""}
                      </span>
                    </div>
                  {/each}
                </div>
              </div>
            {/each}
          </div>
        </section>
      {/if}
    {/if}

    {#if previewRows.length}
      <div class="space-y-1.5">
        <p class="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
          Sample records
        </p>
        <div class="grid gap-3 md:grid-cols-3">
          {#each previewRows as preview, index (index)}
            <div class="min-w-0 rounded-xl border border-border bg-card p-3">
              {#if Object.keys(preview.thumbnails ?? {}).length}
                <div class="mb-2 flex flex-wrap gap-1.5">
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
              <div class="space-y-1 text-xs text-muted-foreground">
                {#each Object.entries(preview.record).slice(0, 6) as [key, value] (key)}
                  <span class="block break-words">
                    <span class="font-medium text-foreground/80">{readableName(key)}:</span>
                    <span class="break-all">{JSON.stringify(value)}</span>
                  </span>
                {/each}
              </div>
            </div>
          {/each}
        </div>
      </div>
    {/if}

    {#if plan.inferred_schema}
      <details class="group rounded-xl border border-border bg-card">
        <summary
          class="cursor-pointer rounded-xl px-5 py-4 text-sm font-medium text-muted-foreground hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          Schema details
        </summary>
        <div class="px-3 pb-3">
          <SchemaPanel schema={plan.inferred_schema} />
        </div>
      </details>
    {/if}
  {/if}
</div>
