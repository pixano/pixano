<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { CaretDown, CaretRight, CheckCircle, FolderOpen, UploadSimple } from "phosphor-svelte";

  import { matchesUpload, preflightLayout } from "./layoutPreflight";
  import LayoutPreviewPanel from "./LayoutPreviewPanel.svelte";
  import { TASK_CARDS } from "./rawSchema";
  import RawSchemaBuilder from "./RawSchemaBuilder.svelte";
  import {
    formatBytes,
    parseAdvancedSpec,
    showsLerobotFields,
    type WizardFields,
  } from "./wizardUtils";
  import { deleteUploadSession } from "$lib/api/ioApi";
  import {
    filterSelection,
    splitFolderSelection,
    uploadFolder,
    type FolderSelection,
    type UploadProgress,
  } from "$lib/api/uploadClient";

  interface Props {
    fields: WizardFields;
    advancedJson: string;
  }

  let { fields = $bindable(), advancedJson = $bindable() }: Props = $props();

  let showAdvanced = $state(false);
  let sourceMode = $state<"upload" | "hub">(fields.intent === "lerobot" ? "hub" : "upload");
  let uploadState = $state<"idle" | "uploading" | "done" | "error">(
    fields.source ? "done" : "idle",
  );
  let uploadError = $state("");
  let selection = $state<FolderSelection | null>(null);
  let progress = $state<UploadProgress | null>(null);
  let fileInput = $state<HTMLInputElement | null>(null);
  let abortController: AbortController | null = null;
  let uploadId = "";
  let uploadedTask = $state(fields.raw.task);

  const advancedError = $derived(parseAdvancedSpec(advancedJson).error);
  const showLerobot = $derived(showsLerobotFields(fields));
  const offersHub = $derived(fields.intent === "lerobot" || fields.intent === "auto");
  const layoutHint = $derived(
    fields.intent === "raw"
      ? (TASK_CARDS.find((card) => card.task === fields.raw.task)?.layoutHint ?? "")
      : "",
  );
  const progressPercent = $derived(
    progress && progress.totalBytes > 0
      ? Math.min(100, Math.round((progress.uploadedBytes / progress.totalBytes) * 100))
      : 0,
  );

  $effect(() => {
    return () => abortController?.abort();
  });

  $effect(() => {
    // Raw uploads are filtered by task; if the user changes the task
    // after picking, the staged files no longer match — drop them so the
    // next pick re-filters. (Guarded so the reset can't re-trigger itself.)
    if (
      fields.intent === "raw" &&
      (uploadState !== "idle" || fields.raw.layout !== null) &&
      fields.raw.task !== uploadedTask
    ) {
      discardStagedUpload();
    }
  });

  function discardStagedUpload() {
    if (uploadId) {
      void deleteUploadSession(uploadId).catch(() => undefined);
      uploadId = "";
    }
    fields.raw.layout = null;
    if (uploadState !== "idle") {
      fields.source = "";
      fields.sourceLabel = "";
      uploadState = "idle";
      selection = null;
      progress = null;
      uploadError = "";
    }
  }

  function setSourceMode(mode: "upload" | "hub") {
    if (mode === sourceMode) return;
    abortController?.abort();
    discardStagedUpload();
    fields.source = "";
    fields.sourceLabel = "";
    sourceMode = mode;
  }

  async function handleFolderPicked(event: Event) {
    const input = event.currentTarget as HTMLInputElement;
    const files = [...(input.files ?? [])];
    input.value = ""; // allow re-picking the same folder
    if (!files.length) return;

    abortController?.abort();
    discardStagedUpload();
    let picked = splitFolderSelection(files);
    if (fields.intent === "raw") {
      // Preflight the layout on the client BEFORE uploading anything: a bad
      // folder structure must not cost a multi-gigabyte upload to discover.
      const layout = preflightLayout(picked.entries, fields.raw.task);
      fields.raw.layout = layout;
      uploadedTask = fields.raw.task;
      if (!layout.ok) {
        uploadState = "idle";
        uploadError = "";
        return; // the layout panel shows what to fix; pick the folder again
      }
      // Upload only the task's media kinds: a stray metadata.jsonl,
      // .DS_Store, or README must not be staged (a metadata.jsonl would flip
      // the source out of media-only mode and import nothing). Frame-folder
      // video sources upload their frame images, not video files.
      picked = filterSelection(picked, (name) =>
        matchesUpload(name, fields.raw.task, layout.encoding),
      );
    }
    if (!picked.entries.length) {
      uploadState = "error";
      uploadError = "The selected folder contains no files.";
      return;
    }
    selection = picked;
    uploadedTask = fields.raw.task;
    uploadState = "uploading";
    uploadError = "";
    progress = {
      uploadedBytes: 0,
      totalBytes: picked.totalBytes,
      uploadedFiles: 0,
      totalFiles: picked.entries.length,
    };
    abortController = new AbortController();
    try {
      const staged = await uploadFolder(
        picked,
        (update) => (progress = update),
        abortController.signal,
      );
      uploadId = staged.uploadId;
      fields.source = staged.source;
      fields.sourceLabel = picked.folderName;
      uploadState = "done";
    } catch (error: unknown) {
      fields.source = "";
      fields.sourceLabel = "";
      if (error instanceof DOMException && error.name === "AbortError") {
        uploadState = "idle";
        selection = null;
      } else {
        uploadState = "error";
        uploadError = error instanceof Error ? error.message : "The upload failed.";
      }
      progress = null;
    }
  }

  function cancelUpload() {
    abortController?.abort();
  }

  const labelClass = "text-xs font-semibold uppercase tracking-widest text-muted-foreground";
  const inputClass =
    "w-full rounded-lg border border-border bg-card px-3 py-2 text-sm text-foreground " +
    "placeholder:text-muted-foreground/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring";
  const segmentClass = (active: boolean) =>
    `rounded-lg border px-3 py-1.5 text-xs font-medium transition-colors ${
      active
        ? "border-primary bg-primary/10 text-primary"
        : "border-border text-muted-foreground hover:border-primary/40"
    }`;
</script>

<div class="px-6 sm:px-7 pb-2 space-y-4">
  <div class="space-y-1.5">
    <p class={labelClass}>Source</p>

    {#if offersHub}
      <div class="flex gap-1.5">
        <button
          type="button"
          class={segmentClass(sourceMode === "hub")}
          onclick={() => setSourceMode("hub")}
        >
          Hugging Face hub
        </button>
        <button
          type="button"
          class={segmentClass(sourceMode === "upload")}
          onclick={() => setSourceMode("upload")}
        >
          Upload a folder
        </button>
      </div>
    {/if}

    {#if offersHub && sourceMode === "hub"}
      <input
        id="wizard-source"
        type="text"
        class={inputClass}
        placeholder="org/name (Hugging Face dataset id)"
        bind:value={fields.source}
      />
      <p class="text-xs text-muted-foreground">
        The dataset id on the Hugging Face hub; only the selected episodes are downloaded.
      </p>
    {:else}
      <input
        type="file"
        class="hidden"
        webkitdirectory
        multiple
        bind:this={fileInput}
        onchange={handleFolderPicked}
      />
      {#if uploadState === "idle" || uploadState === "error"}
        <button
          type="button"
          class="flex w-full items-center gap-3 rounded-xl border border-dashed border-border bg-card p-4 text-left hover:border-primary/50"
          onclick={() => fileInput?.click()}
        >
          <UploadSimple weight="regular" class="h-5 w-5 shrink-0 text-primary" />
          <span class="min-w-0 flex-1">
            <span class="block text-sm font-medium text-foreground">
              Choose a folder on your computer…
            </span>
            <span class="mt-0.5 block text-xs text-muted-foreground">
              The folder uploads to Pixano and imports from there — nothing else to configure.
            </span>
            {#if layoutHint}
              <pre
                class="mt-2 overflow-x-auto rounded-lg bg-surface-2 px-2.5 py-2 font-mono text-[10px] leading-relaxed text-muted-foreground">{layoutHint}</pre>
            {/if}
          </span>
        </button>
        {#if uploadError}
          <p class="text-xs text-destructive">{uploadError}</p>
        {/if}
      {:else if uploadState === "uploading" && selection && progress}
        <div class="space-y-2 rounded-xl border border-border bg-card p-4">
          <div class="flex items-center justify-between gap-2 text-sm">
            <span class="flex min-w-0 items-center gap-2 text-foreground">
              <FolderOpen weight="regular" class="h-4 w-4 shrink-0 text-primary" />
              <span class="truncate font-medium">{selection.folderName}</span>
            </span>
            <button
              type="button"
              class="shrink-0 text-xs text-muted-foreground hover:text-destructive"
              onclick={cancelUpload}
            >
              Cancel
            </button>
          </div>
          <div class="h-1.5 w-full overflow-hidden rounded-full bg-border">
            <div
              class="h-full rounded-full bg-primary transition-all"
              style="width: {progressPercent}%"
            ></div>
          </div>
          <p class="text-xs tabular-nums text-muted-foreground">
            Uploading {progress.uploadedFiles}/{progress.totalFiles} files — {formatBytes(
              progress.uploadedBytes,
            ) || "0 B"} of {formatBytes(progress.totalBytes)} ({progressPercent}%)
          </p>
        </div>
      {:else if uploadState === "done" && selection}
        <div
          class="flex items-center justify-between gap-2 rounded-xl border border-border bg-card p-4"
        >
          <span class="flex min-w-0 items-center gap-2 text-sm text-foreground">
            <CheckCircle
              weight="fill"
              class="h-4 w-4 shrink-0 text-green-600 dark:text-green-400"
            />
            <span class="truncate font-medium">{selection.folderName}</span>
            <span class="shrink-0 text-xs text-muted-foreground">
              {selection.entries.length} files · {formatBytes(selection.totalBytes)} uploaded
            </span>
          </span>
          <button
            type="button"
            class="shrink-0 text-xs text-muted-foreground hover:text-foreground"
            onclick={() => fileInput?.click()}
          >
            Replace…
          </button>
        </div>
      {/if}
    {/if}

    {#if fields.intent === "raw" && fields.raw.layout}
      <LayoutPreviewPanel layout={fields.raw.layout} />
    {/if}
  </div>

  <div class="grid gap-4 sm:grid-cols-2">
    <div class="space-y-1.5">
      <label class={labelClass} for="wizard-name">Dataset name (optional)</label>
      <input
        id="wizard-name"
        type="text"
        class={inputClass}
        placeholder={fields.sourceLabel || "Defaults to the folder name"}
        bind:value={fields.name}
      />
    </div>
    <div class="space-y-1.5">
      <label class={labelClass} for="wizard-mode">If the dataset exists</label>
      <select id="wizard-mode" class={inputClass} bind:value={fields.mode}>
        <option value="create">Fail (create only)</option>
        <option value="overwrite">Overwrite it</option>
      </select>
    </div>
  </div>

  {#if fields.intent === "raw"}
    <RawSchemaBuilder bind:raw={fields.raw} />
  {/if}

  {#if showLerobot}
    <div class="grid gap-4 sm:grid-cols-2">
      <div class="space-y-1.5">
        <label class={labelClass} for="wizard-episodes">Episodes (optional)</label>
        <input
          id="wizard-episodes"
          type="text"
          class={inputClass}
          placeholder="e.g. 0:4 or 1,3,7"
          bind:value={fields.episodes}
        />
      </div>
      <div class="space-y-1.5">
        <label class={labelClass} for="wizard-max-frames">Max frames / episode (optional)</label>
        <input
          id="wizard-max-frames"
          type="number"
          min="1"
          class={inputClass}
          placeholder="All frames"
          bind:value={fields.maxFrames}
        />
      </div>
    </div>
  {/if}

  <div class="rounded-xl border border-border">
    <button
      type="button"
      class="flex w-full items-center gap-2 px-4 py-3 text-xs font-semibold uppercase tracking-widest text-muted-foreground hover:text-foreground"
      onclick={() => (showAdvanced = !showAdvanced)}
    >
      {#if showAdvanced}
        <CaretDown weight="bold" class="h-3.5 w-3.5" />
      {:else}
        <CaretRight weight="bold" class="h-3.5 w-3.5" />
      {/if}
      Advanced spec (JSON)
    </button>
    {#if showAdvanced}
      <div class="space-y-2 border-t border-border p-4">
        <p class="text-xs text-muted-foreground">
          Optional overrides merged over the fields above — the same keys as
          <span class="font-mono">dataset.yaml</span>
          (dataset, schema with any attributes, ids, options, media). A
          <span class="font-mono">schema</span>
          key here replaces the one built by the form.
        </p>
        <textarea
          class="h-36 w-full resize-y rounded-lg border border-border bg-card p-3 font-mono text-xs text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          placeholder={'{\n  "schema": {"record": {"attrs": {"weather": "str"}}}\n}'}
          bind:value={advancedJson}
        ></textarea>
        {#if advancedError}
          <p class="text-xs text-destructive">{advancedError}</p>
        {/if}
      </div>
    {/if}
  </div>
</div>
