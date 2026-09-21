<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import {
    ArrowRight,
    CheckCircle,
    CloudArrowDown,
    FolderOpen,
    Info,
    UploadSimple,
  } from "phosphor-svelte";
  import { onDestroy } from "svelte";

  import { matchesUpload, preflightLayout } from "./layoutPreflight";
  import LayoutPreviewPanel from "./LayoutPreviewPanel.svelte";
  import { TASK_CARDS } from "./rawSchema";
  import RawVideoOptions from "./RawVideoOptions.svelte";
  import type { WizardSourceState } from "./sourceState";
  import { WIZARD_INPUT_CLASS, WIZARD_LABEL_CLASS } from "./wizardStyles";
  import {
    formatBytes,
    parseEpisodeSelection,
    showsLerobotFields,
    validateLerobotMaxFrames,
    type WizardFields,
  } from "./wizardUtils";
  import { deleteUploadSession } from "$lib/api/ioApi";
  import { filterSelection, splitFolderSelection, uploadFolder } from "$lib/api/uploadClient";

  interface Props {
    fields: WizardFields;
    sourceState: WizardSourceState;
    notice?: string;
    onChangeTask: () => void;
  }
  let {
    fields = $bindable(),
    sourceState = $bindable(),
    notice = $bindable(""),
    onChangeTask,
  }: Props = $props();

  let fileInput = $state<HTMLInputElement | null>(null);
  let abortController: AbortController | null = null;
  let uploadToken = 0;

  const showLerobot = $derived(showsLerobotFields(fields));
  const maxFramesError = $derived(validateLerobotMaxFrames(fields.maxFrames));
  const episodesError = $derived(parseEpisodeSelection(fields.episodes).error);
  const offersHub = $derived(fields.intent === "lerobot" || fields.intent === "auto");
  const layoutHint = $derived(
    fields.intent === "raw"
      ? (TASK_CARDS.find((card) => card.task === fields.raw.task)?.layoutHint ?? "")
      : "",
  );
  const progressPercent = $derived(
    sourceState.progress && sourceState.progress.totalBytes > 0
      ? Math.min(
          100,
          Math.round((sourceState.progress.uploadedBytes / sourceState.progress.totalBytes) * 100),
        )
      : 0,
  );

  onDestroy(() => {
    uploadToken++;
    abortController?.abort();
  });

  /** Format/task changes and source replacement discard only the staged source. */
  export function resetSource(mode: "upload" | "hub" = sourceState.mode) {
    uploadToken++;
    abortController?.abort();
    abortController = null;
    notice = "";
    if (sourceState.uploadId) void deleteUploadSession(sourceState.uploadId).catch(() => undefined);
    sourceState.mode = mode;
    sourceState.uploadId = "";
    sourceState.status = "idle";
    sourceState.error = "";
    sourceState.summary = null;
    sourceState.progress = null;
    fields.source = "";
    fields.sourceLabel = "";
    fields.raw.layout = null;
  }

  async function handleFolderPicked(event: Event) {
    const input = event.currentTarget as HTMLInputElement;
    const files = [...(input.files ?? [])];
    input.value = "";
    if (!files.length) return;

    resetSource("upload");
    const token = uploadToken;
    let picked = splitFolderSelection(files);
    if (fields.intent === "raw") {
      const layout = preflightLayout(picked.entries, fields.raw.task);
      fields.raw.layout = layout;
      if (!layout.ok) return;
      picked = filterSelection(picked, (name) =>
        matchesUpload(name, fields.raw.task, layout.encoding),
      );
    }
    if (!picked.entries.length) {
      sourceState.status = "error";
      sourceState.error = "The selected folder contains no files.";
      return;
    }
    sourceState.summary = {
      folderName: picked.folderName,
      fileCount: picked.entries.length,
      totalBytes: picked.totalBytes,
    };
    sourceState.status = "uploading";
    sourceState.progress = {
      uploadedBytes: 0,
      totalBytes: picked.totalBytes,
      uploadedFiles: 0,
      totalFiles: picked.entries.length,
    };
    abortController = new AbortController();
    try {
      const staged = await uploadFolder(
        picked,
        (update) => {
          if (token === uploadToken) sourceState.progress = update;
        },
        abortController.signal,
      );
      if (token !== uploadToken) {
        void deleteUploadSession(staged.uploadId).catch(() => undefined);
        return;
      }
      sourceState.uploadId = staged.uploadId;
      fields.source = staged.source;
      fields.sourceLabel = picked.folderName;
      sourceState.status = "done";
    } catch (error: unknown) {
      if (token !== uploadToken) return;
      fields.source = "";
      fields.sourceLabel = "";
      if (error instanceof DOMException && error.name === "AbortError") {
        sourceState.status = "idle";
        sourceState.summary = null;
      } else {
        sourceState.status = "error";
        sourceState.error = error instanceof Error ? error.message : "The upload failed.";
      }
      sourceState.progress = null;
    }
  }

  const taskTitle = $derived(
    TASK_CARDS.find((card) => card.task === fields.raw.task)?.title ?? "Image annotation",
  );
  const labelClass = WIZARD_LABEL_CLASS;
  const inputClass = WIZARD_INPUT_CLASS;
  const segmentClass = (active: boolean) =>
    `inline-flex h-8 items-center justify-center gap-2 rounded-md px-3 text-xs font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${active ? "bg-card text-foreground shadow-sm ring-1 ring-border/60" : "text-muted-foreground hover:text-foreground"}`;
</script>

<div class="space-y-6">
  <div class="space-y-3">
    <div class="flex flex-wrap items-center justify-between gap-2">
      <p class={labelClass}>Data location</p>
      {#if fields.intent === "raw"}<button
          type="button"
          class="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          onclick={onChangeTask}
          aria-label="Change annotation task"
        >
          {taskTitle}<ArrowRight size={12} />
        </button>{/if}
    </div>
    {#if notice}<p
        class="flex items-start gap-2 text-xs leading-relaxed text-muted-foreground"
        role="status"
      >
        <Info size={16} class="shrink-0" />{notice}
      </p>{/if}
    {#if offersHub}
      <div
        class="inline-flex flex-wrap gap-1 rounded-lg border border-border/60 bg-muted/40 p-1"
        aria-label="Data location"
      >
        <button
          type="button"
          class={segmentClass(sourceState.mode === "hub")}
          aria-pressed={sourceState.mode === "hub"}
          onclick={() => {
            if (sourceState.mode !== "hub") resetSource("hub");
          }}
        >
          <CloudArrowDown size={16} />Hugging Face Hub
        </button>
        <button
          type="button"
          class={segmentClass(sourceState.mode === "upload")}
          aria-pressed={sourceState.mode === "upload"}
          onclick={() => {
            if (sourceState.mode !== "upload") resetSource("upload");
          }}
        >
          <FolderOpen size={16} />Upload a folder
        </button>
      </div>
    {/if}

    {#if offersHub && sourceState.mode === "hub"}
      <label for="wizard-source" class="sr-only">Hugging Face dataset ID</label>
      <input
        id="wizard-source"
        type="text"
        class={inputClass}
        placeholder="organization/dataset-name"
        bind:value={fields.source}
        aria-describedby="wizard-source-help"
      />
      <p id="wizard-source-help" class="text-xs leading-relaxed text-muted-foreground">
        Media downloads start with the import.
      </p>
    {:else}
      <input
        type="file"
        class="hidden"
        webkitdirectory
        multiple
        bind:this={fileInput}
        onchange={handleFolderPicked}
        aria-label="Dataset folder"
      />
      {#if sourceState.status === "idle" || sourceState.status === "error"}
        <button
          type="button"
          class="group flex w-full items-center gap-3 rounded-xl border border-dashed border-border bg-card/50 p-5 text-left transition-colors hover:border-primary/40 hover:bg-primary/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          onclick={() => fileInput?.click()}
        >
          <span
            class="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-muted/50 text-muted-foreground group-hover:text-primary"
          >
            <UploadSimple weight="regular" size={22} />
          </span>
          <span class="min-w-0 flex-1">
            <span class="block text-sm font-medium text-foreground">Choose a folder</span>
            <span class="mt-1 block text-xs text-muted-foreground">
              Upload a local dataset directory.
            </span>
          </span>
        </button>
        {#if sourceState.error}<p class="text-sm text-destructive" role="alert">
            {sourceState.error}
          </p>{/if}
      {:else if sourceState.status === "uploading" && sourceState.summary && sourceState.progress}
        <div class="space-y-3 rounded-xl border border-border bg-card p-4" role="status">
          <div class="flex items-center justify-between gap-2 text-sm">
            <span class="flex min-w-0 items-center gap-2 text-foreground">
              <FolderOpen class="h-5 w-5 shrink-0 text-primary" />
              <span class="truncate font-medium">{sourceState.summary.folderName}</span>
            </span>
            <button
              type="button"
              class="shrink-0 text-sm text-muted-foreground hover:text-destructive"
              onclick={() => resetSource()}
            >
              Cancel upload
            </button>
          </div>
          <div
            class="h-1.5 w-full overflow-hidden rounded-full bg-border"
            role="progressbar"
            aria-label="Folder upload"
            aria-valuenow={progressPercent}
            aria-valuemin={0}
            aria-valuemax={100}
          >
            <div
              class="h-full rounded-full bg-primary transition-all"
              style="width: {progressPercent}%"
            ></div>
          </div>
          <p class="text-sm tabular-nums text-muted-foreground">
            Uploading {sourceState.progress.uploadedFiles}/{sourceState.progress.totalFiles} files ·
            {progressPercent}%
          </p>
        </div>
      {:else if sourceState.status === "done" && sourceState.summary}
        <div
          class="flex items-center justify-between gap-3 rounded-xl border border-border bg-card p-4"
        >
          <div class="flex min-w-0 items-center gap-3">
            <CheckCircle
              weight="fill"
              class="h-5 w-5 shrink-0 text-green-600 dark:text-green-400"
            />
            <div class="min-w-0">
              <p class="truncate text-sm font-medium text-foreground">
                {sourceState.summary.folderName}
              </p>
              <p class="mt-1 text-xs text-muted-foreground">
                {sourceState.summary.fileCount} files · {formatBytes(
                  sourceState.summary.totalBytes,
                )} uploaded
              </p>
            </div>
          </div>
          <button
            type="button"
            class="shrink-0 text-sm text-primary hover:underline"
            onclick={() => fileInput?.click()}
          >
            Replace folder
          </button>
        </div>
      {/if}
      {#if layoutHint}
        <details class="text-sm text-muted-foreground">
          <summary class="cursor-pointer hover:text-foreground">Expected folder structure</summary>
          <pre
            class="mt-2 overflow-x-auto rounded-lg bg-surface-2 p-3 text-xs leading-relaxed">{layoutHint}</pre>
          <p class="mt-2">Optional split directories: train, val, test.</p>
        </details>
      {/if}
    {/if}
    {#if fields.intent === "raw" && fields.raw.layout}<LayoutPreviewPanel
        layout={fields.raw.layout}
      />{/if}
  </div>

  <div class="space-y-2">
    <label class={labelClass} for="wizard-name">
      Dataset name <span class="font-normal text-muted-foreground">(optional)</span>
    </label>
    <input
      id="wizard-name"
      type="text"
      class={inputClass}
      placeholder={fields.sourceLabel || "Source name"}
      bind:value={fields.name}
    />
  </div>

  {#if fields.intent === "raw" && fields.raw.task === "video"}<RawVideoOptions
      bind:raw={fields.raw}
    />{/if}

  {#if showLerobot}
    <fieldset class="min-w-0 space-y-3">
      <legend class="text-sm font-medium text-foreground">
        Import range <span class="font-normal text-muted-foreground">(optional)</span>
      </legend>
      <div class="grid grid-cols-2 gap-3">
        <div class="min-w-0 space-y-2">
          <label class="text-xs text-muted-foreground" for="wizard-episodes">Episodes</label>
          <input
            id="wizard-episodes"
            type="text"
            class={inputClass}
            placeholder="All episodes"
            bind:value={fields.episodes}
            aria-invalid={!!episodesError}
            aria-describedby="wizard-episodes-help"
          />
        </div>
        <div class="min-w-0 space-y-2">
          <label class="text-xs text-muted-foreground" for="wizard-max-frames">
            Frames per episode
          </label>
          <input
            id="wizard-max-frames"
            type="text"
            inputmode="numeric"
            class={inputClass}
            placeholder="All frames"
            bind:value={fields.maxFrames}
            aria-invalid={!!maxFramesError}
            aria-describedby={maxFramesError ? "wizard-max-frames-error" : undefined}
          />
        </div>
      </div>
      <p id="wizard-episodes-help" class="text-xs leading-relaxed text-muted-foreground">
        Episodes: 0:4 (inclusive range) or 1,3,7 (indices). Frames are sampled across each episode.
      </p>
      {#if episodesError}<p class="text-xs text-destructive" role="alert">{episodesError}</p>{/if}
      {#if maxFramesError}<p
          id="wizard-max-frames-error"
          class="text-xs text-destructive"
          role="alert"
        >
          {maxFramesError}
        </p>{/if}
    </fieldset>
  {/if}
  <div class="border-t border-border/60 pt-4">
    <label class="inline-flex cursor-pointer items-center gap-2 text-sm text-foreground">
      <input
        id="wizard-overwrite"
        type="checkbox"
        class="size-4 accent-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
        checked={fields.mode === "overwrite"}
        onchange={(event) => {
          fields.mode = event.currentTarget.checked ? "overwrite" : "create";
        }}
      />
      Overwrite existing dataset
    </label>
  </div>
</div>
