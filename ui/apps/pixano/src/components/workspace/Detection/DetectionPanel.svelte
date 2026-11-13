<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { Plus, Sparkle, X } from "phosphor-svelte";

  import { collectExemplars, collectNegatives } from "$lib/detection/detection";
  import { currentItemSaveCoordinator } from "$lib/stores/appStores.svelte";
  import {
    closeDetectionSession,
    detectionSession,
    isAddingDetectionExamples,
    resetDetectionSession,
    resolveDetectionImages,
    resolveDetectionLabelField,
    runDetection,
    selectDetectionView,
    startAddingDetectionExamples,
    stopAddingDetectionExamples,
    updateDetectionParams,
  } from "$lib/stores/detectionStore.svelte";
  import {
    detectionModels,
    inferenceServerStore,
    selectedDetectionModel,
  } from "$lib/stores/inferenceStores.svelte";
  import { annotations, entities, itemMetas } from "$lib/stores/workspaceStores.svelte";
  import {
    getInferenceModelKey,
    isSameInferenceModel,
    supportsExemplars,
    supportsNegativeExemplars,
  } from "$lib/types/inference";
  import { AiProcessingBadge, cn, IconButton, ModelSelectBadge } from "$lib/ui";
  import { getWorkspaceContext } from "$lib/workspace/context";

  const workspace = getWorkspaceContext();

  const session = $derived(detectionSession.value);
  const models = $derived(detectionModels.value);
  const selectedModel = $derived(
    models.find((model) => isSameInferenceModel(model, selectedDetectionModel.value)) ?? null,
  );
  const readsExemplars = $derived(supportsExemplars(selectedModel));
  const readsNegatives = $derived(supportsNegativeExemplars(selectedModel));
  const images = $derived(resolveDetectionImages());
  const image = $derived(
    images.find((candidate) => candidate.viewName === session.viewName) ?? null,
  );
  const labelField = $derived(resolveDetectionLabelField(workspace.manifest));
  const labelValues = $derived(
    labelField ? (workspace.featureValues?.objects?.[labelField]?.values ?? []) : [],
  );
  const exemplarCount = $derived(
    image && readsExemplars
      ? collectExemplars({
          annotations: annotations.value,
          entities: entities.value,
          image,
          labelField,
          className: session.params.className,
        }).length
      : 0,
  );
  const negativeCount = $derived(
    image && readsNegatives && exemplarCount > 0
      ? collectNegatives(session.proposals, annotations.value, image.viewName).length
      : 0,
  );
  const hasClass = $derived(session.params.className.trim().length > 0);
  const addingExamples = $derived(isAddingDetectionExamples.value);
  const canRun = $derived(
    !!selectedModel && !!image && session.phase !== "running" && (hasClass || exemplarCount > 0),
  );
  const modelLabel = $derived.by(() => {
    if (selectedModel) return selectedModel.name;
    if (inferenceServerStore.value.status === "loading") return "Loading";
    if (!inferenceServerStore.value.connected) return "No server";
    return "No detection model";
  });

  // Another record: what this session added belongs to the previous one.
  $effect(() => {
    const recordId = itemMetas.value?.item.id;
    if (recordId && session.target && recordId !== session.target.recordId) resetDetectionSession();
  });

  function selectModel(key: string): void {
    const model = models.find((candidate) => getInferenceModelKey(candidate) === key);
    if (model) selectedDetectionModel.value = model;
  }

  async function run(): Promise<void> {
    if (!selectedModel) return;
    stopAddingDetectionExamples();
    const result = await runDetection({
      model: selectedModel,
      manifest: workspace.manifest,
      featureValues: workspace.featureValues,
    });
    if (result && result.added > 0) void currentItemSaveCoordinator.requestSave();
  }

  function percent(value: number): string {
    return `${Math.round(value * 100)}%`;
  }

  function plural(count: number, word: string): string {
    return `${count} ${word}${count === 1 ? "" : "s"}`;
  }

  const buttonClass =
    "rounded-lg border px-3 py-1.5 text-xs font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-50";
  const primaryButtonClass = cn(
    buttonClass,
    "border-primary/60 bg-primary text-primary-foreground hover:bg-primary/90",
  );
  const secondaryButtonClass = cn(
    buttonClass,
    "border-border/60 bg-background text-foreground hover:bg-muted/60",
  );
</script>

<div class="flex h-full flex-col overflow-hidden">
  <div class="flex shrink-0 items-center gap-2 border-b border-border/50 px-3 py-2">
    <Sparkle class="h-4 w-4 text-primary" />
    <span class="flex-1 text-xs font-semibold">Detect objects</span>
    <IconButton tooltipContent="Close" onclick={closeDetectionSession} class="h-7 w-7">
      <X class="h-3.5 w-3.5" />
    </IconButton>
  </div>

  <div class="min-h-0 flex-1 overflow-y-auto px-3 py-3 text-xs">
    {#if session.phase === "error" && session.error}
      <p
        class="mb-3 rounded-md border border-destructive/40 bg-destructive/10 px-2 py-1.5 text-destructive"
      >
        {session.error}
      </p>
    {/if}

    <div class="flex flex-col gap-3">
      <label class="flex flex-col gap-1">
        <span class="font-medium text-muted-foreground">Model</span>
        <ModelSelectBadge
          {models}
          selectedModelKey={selectedModel ? getInferenceModelKey(selectedModel) : ""}
          disabled={models.length === 0 || session.phase === "running"}
          label={modelLabel}
          onValueChange={selectModel}
        />
      </label>

      {#if images.length > 1}
        <label class="flex flex-col gap-1">
          <span class="font-medium text-muted-foreground">View</span>
          <select
            class="rounded-md border border-border/60 bg-background px-2 py-1"
            value={session.viewName ?? ""}
            disabled={session.phase === "running"}
            onchange={(event) => selectDetectionView(event.currentTarget.value)}
          >
            {#each images as candidate (candidate.viewName)}
              <option value={candidate.viewName}>{candidate.viewName}</option>
            {/each}
          </select>
        </label>
      {/if}

      <label class="flex flex-col gap-1">
        <span class="font-medium text-muted-foreground">
          Class{labelField ? ` (${labelField})` : ""}
        </span>
        <input
          type="text"
          list="detection-class-values"
          class="rounded-md border border-border/60 bg-background px-2 py-1"
          placeholder="screw"
          value={session.params.className}
          oninput={(event) => updateDetectionParams({ className: event.currentTarget.value })}
        />
        <datalist id="detection-class-values">
          {#each labelValues as value (value)}
            <option {value}></option>
          {/each}
        </datalist>
      </label>

      <label class="flex flex-col gap-1">
        <span class="font-medium text-muted-foreground">
          Detection threshold · {percent(session.params.boxThreshold)}
        </span>
        <input
          type="range"
          min="0"
          max="1"
          step="0.01"
          value={session.params.boxThreshold}
          oninput={(event) =>
            updateDetectionParams({ boxThreshold: Number(event.currentTarget.value) })}
        />
      </label>

      {#if readsExemplars}
        <div class="flex flex-col gap-1 rounded-md border border-border/50 bg-muted/20 px-2 py-1.5">
          <span>
            {#if exemplarCount > 0}
              {plural(exemplarCount, "example")}
              {hasClass && labelField ? `of "${session.params.className.trim()}"` : ""} on this image{#if readsNegatives && negativeCount > 0},
                {plural(negativeCount, "rejected proposal")} to avoid{/if}.
            {:else}
              Box a few {hasClass ? `"${session.params.className.trim()}"` : "objects"} on this image{labelField
                ? `, with ${labelField} "${hasClass ? session.params.className.trim() : "…"}"`
                : ""}, then find more like them.
            {/if}
          </span>
          <label class={cn("flex items-center gap-2", !hasClass && "opacity-50")}>
            <input
              type="checkbox"
              checked={session.params.classAsText}
              disabled={!hasClass}
              onchange={(event) =>
                updateDetectionParams({ classAsText: event.currentTarget.checked })}
            />
            <span>Also use the class name as text</span>
          </label>
          <span class="text-muted-foreground">
            Unticked, the examples alone decide: the name can make look-alikes score as high.
          </span>
          {#if addingExamples}
            <p class="rounded-md border border-primary/40 bg-primary/10 px-2 py-1.5">
              Draw a box around each "{session.params.className.trim()}": it is saved as an example
              as soon as it is drawn.
            </p>
          {/if}
          <button
            type="button"
            class={cn(addingExamples ? primaryButtonClass : secondaryButtonClass, "self-start")}
            disabled={!hasClass || session.phase === "running"}
            title={hasClass ? undefined : "Type a class first"}
            onclick={() =>
              addingExamples ? stopAddingDetectionExamples() : startAddingDetectionExamples()}
          >
            <Plus class="mr-1 inline h-3 w-3" />
            {addingExamples ? "Done adding examples" : "Add examples"}
          </button>
        </div>
      {/if}

      <div class="flex gap-2 pt-1">
        <button type="button" class={primaryButtonClass} disabled={!canRun} onclick={run}>
          {exemplarCount > 0 ? "Find more like these" : "Detect"}
        </button>
        <button type="button" class={secondaryButtonClass} onclick={closeDetectionSession}>
          Close
        </button>
      </div>

      {#if session.phase === "running"}
        <AiProcessingBadge message="Detecting..." />
      {:else if session.lastRun}
        <p class="text-muted-foreground">
          {plural(session.lastRun.added, "proposal")} added{#if session.lastRun.duplicates > 0},
            {session.lastRun.duplicates} already on the image{/if}. They are pending: close this
          panel to accept or reject them in the Entities tab, then come back for more. Those
          rejected are not proposed again.
        </p>
      {/if}
    </div>
  </div>
</div>
