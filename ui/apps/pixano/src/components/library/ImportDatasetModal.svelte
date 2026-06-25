<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import PrimaryButton from "$components/ui/molecules/PrimaryButton.svelte";
  import { AlertDialog } from "bits-ui";
  import { CheckCircle, CircleNotch, FolderOpen, WarningCircle } from "phosphor-svelte";

  import { invalidateAll } from "$app/navigation";
  import { getImportJob, startDatasetImport } from "$lib/api/datasets";
  import {
    BLOCKING_ALERT_ACTIONS_CLASS,
    BLOCKING_ALERT_CONTENT_CLASS,
    BLOCKING_ALERT_HEADER_CLASS,
    BLOCKING_ALERT_OVERLAY_CLASS,
    BLOCKING_ALERT_SECONDARY_BUTTON_CLASS,
    BLOCKING_ALERT_SUPPORTING_TEXT_CLASS,
    BLOCKING_ALERT_TITLE_CLASS,
    BLOCKING_ALERT_VIEWPORT_CLASS,
  } from "$lib/constants/modalConstants";

  interface Props {
    onClose: () => void;
  }

  const IMPORT_TYPES = [
    {
      id: "unlabeled_images",
      label: "Unlabeled Images Folder",
      description: "Import a flat folder of image files (JPG, PNG, BMP, TIFF…)",
    },
    {
      id: "unlabeled_videos",
      label: "Unlabeled Videos Folder",
      description: "Import a flat folder of video files (MP4, AVI, MOV, MKV…)",
    },
  ] as const;

  let { onClose }: Props = $props();

  let open = $state(true);
  let selectedType = $state<string>(IMPORT_TYPES[0].id);
  let sourceDir = $state("");
  let datasetName = $state("");
  let phase = $state<"form" | "running" | "done" | "error">("form");
  let statusMessage = $state("");
  let jobId = $state<string | null>(null);
  let pollHandle = $state<ReturnType<typeof setInterval> | null>(null);

  const previouslyFocusedElement: HTMLElement | null =
    typeof document !== "undefined" && document.activeElement instanceof HTMLElement
      ? document.activeElement
      : null;

  const canSubmit = $derived(sourceDir.trim().length > 0 && phase === "form");

  function stopPolling() {
    if (pollHandle !== null) {
      clearInterval(pollHandle);
      pollHandle = null;
    }
  }

  async function handleSubmit() {
    if (!canSubmit) return;
    phase = "running";
    statusMessage = "Starting import…";

    try {
      const job = await startDatasetImport(sourceDir.trim(), selectedType, datasetName.trim());
      jobId = job.job_id;
      statusMessage = job.message || "Import started…";

      pollHandle = setInterval(async () => {
        if (!jobId) return;
        try {
          const status = await getImportJob(jobId);
          statusMessage = status.message;
          if (status.status === "done") {
            stopPolling();
            phase = "done";
            await invalidateAll();
          } else if (status.status === "error") {
            stopPolling();
            phase = "error";
          }
        } catch {
          stopPolling();
          phase = "error";
          statusMessage = "Lost connection to server.";
        }
      }, 2000);
    } catch (err: unknown) {
      phase = "error";
      statusMessage = err instanceof Error ? err.message : "Unexpected error starting import.";
    }
  }

  function handleClose() {
    stopPolling();
    open = false;
  }

  function handleRetry() {
    jobId = null;
    phase = "form";
    statusMessage = "";
  }

  function handleOpenChange(nextOpen: boolean) {
    if (!nextOpen && phase === "running") {
      open = true;
      return;
    }
    open = nextOpen;
  }

  function handleOpenChangeComplete(nextOpen: boolean) {
    if (nextOpen) return;
    stopPolling();
    onClose();
  }

  function handleCloseAutoFocus(event: Event) {
    event.preventDefault();
    if (previouslyFocusedElement && previouslyFocusedElement.isConnected) {
      previouslyFocusedElement.focus({ preventScroll: true });
    }
  }
</script>

<AlertDialog.Root
  {open}
  onOpenChange={handleOpenChange}
  onOpenChangeComplete={handleOpenChangeComplete}
>
  <AlertDialog.Portal>
    <AlertDialog.Overlay class={BLOCKING_ALERT_OVERLAY_CLASS} />

    <div class={BLOCKING_ALERT_VIEWPORT_CLASS}>
      <div class="flex min-h-full items-center justify-center">
        <AlertDialog.Content
          class={BLOCKING_ALERT_CONTENT_CLASS}
          trapFocus={true}
          preventScroll={true}
          onEscapeKeydown={(e) => {
            if (phase !== "running") {
              e.preventDefault();
              handleClose();
            } else {
              e.preventDefault();
            }
          }}
          onCloseAutoFocus={handleCloseAutoFocus}
        >
          <div class="pointer-events-none absolute inset-x-0 top-0 h-px bg-primary/15"></div>

          <div class={BLOCKING_ALERT_HEADER_CLASS}>
            <AlertDialog.Title class={BLOCKING_ALERT_TITLE_CLASS}>Import Dataset</AlertDialog.Title>
            <AlertDialog.Description class={BLOCKING_ALERT_SUPPORTING_TEXT_CLASS}>
              <p>Select an import type and provide the path to your data folder on the server.</p>
            </AlertDialog.Description>
          </div>

          {#if phase === "form"}
            <!-- Import type selector -->
            <div class="px-6 sm:px-7 pb-2 space-y-3">
              <p class="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
                Import type
              </p>
              <div class="space-y-2">
                {#each IMPORT_TYPES as t}
                  <label
                    class="flex items-start gap-3 rounded-xl border px-4 py-3 cursor-pointer transition-colors duration-150
                      {selectedType === t.id
                      ? 'border-primary/40 bg-primary/5'
                      : 'border-border/50 bg-background/40 hover:border-border hover:bg-muted/30'}"
                  >
                    <input
                      type="radio"
                      name="import-type"
                      value={t.id}
                      bind:group={selectedType}
                      class="mt-0.5 accent-primary"
                    />
                    <span class="flex flex-col gap-0.5">
                      <span class="text-sm font-semibold text-foreground">{t.label}</span>
                      <span class="text-xs text-muted-foreground">{t.description}</span>
                    </span>
                  </label>
                {/each}
              </div>
            </div>

            <!-- Source folder path -->
            <div class="px-6 sm:px-7 pb-2 space-y-2">
              <label
                for="import-source-dir"
                class="text-xs font-semibold uppercase tracking-widest text-muted-foreground"
              >
                Source folder path
              </label>
              <div class="relative flex items-center">
                <FolderOpen
                  weight="regular"
                  class="absolute left-3 h-4 w-4 text-muted-foreground/60 pointer-events-none"
                />
                <input
                  id="import-source-dir"
                  type="text"
                  placeholder="/path/to/my/images"
                  bind:value={sourceDir}
                  class="w-full h-10 pl-9 pr-4 rounded-xl bg-muted/50 border border-border font-mono text-sm
                    text-foreground placeholder-muted-foreground/50 focus:outline-none focus:ring-2
                    focus:ring-primary/20 focus:bg-background transition-all duration-200"
                />
              </div>
              <p class="text-[11px] text-muted-foreground/70">
                Absolute path to the folder on the machine running the Pixano server.
              </p>
            </div>

            <!-- Optional dataset name -->
            <div class="px-6 sm:px-7 pb-5 space-y-2">
              <label
                for="import-dataset-name"
                class="text-xs font-semibold uppercase tracking-widest text-muted-foreground"
              >
                Dataset name <span class="font-normal normal-case tracking-normal">(optional)</span>
              </label>
              <input
                id="import-dataset-name"
                type="text"
                placeholder="Defaults to folder name"
                bind:value={datasetName}
                class="w-full h-10 px-4 rounded-xl bg-muted/50 border border-border text-sm
                  text-foreground placeholder-muted-foreground/50 focus:outline-none focus:ring-2
                  focus:ring-primary/20 focus:bg-background transition-all duration-200"
              />
            </div>
          {:else if phase === "running"}
            <div class="px-6 sm:px-7 pb-5">
              <div
                class="flex items-center gap-3 rounded-xl border border-border/50 bg-background/55 px-4 py-3 text-sm text-muted-foreground"
              >
                <CircleNotch weight="regular" class="h-4 w-4 shrink-0 animate-spin text-primary" />
                <span>{statusMessage}</span>
              </div>
            </div>
          {:else if phase === "done"}
            <div class="px-6 sm:px-7 pb-5">
              <div
                class="flex items-center gap-3 rounded-xl border border-green-500/20 bg-green-500/8 px-4 py-3 text-sm text-green-600 dark:text-green-400"
              >
                <CheckCircle weight="regular" class="h-4 w-4 shrink-0" />
                <span>{statusMessage}</span>
              </div>
            </div>
          {:else if phase === "error"}
            <div class="px-6 sm:px-7 pb-5">
              <div
                class="flex items-center gap-3 rounded-xl border border-destructive/20 bg-destructive/8 px-4 py-3 text-sm text-destructive"
              >
                <WarningCircle weight="regular" class="h-4 w-4 shrink-0" />
                <span>{statusMessage}</span>
              </div>
            </div>
          {/if}

          <div class={BLOCKING_ALERT_ACTIONS_CLASS}>
            {#if phase === "form" || phase === "error"}
              <button
                type="button"
                class={BLOCKING_ALERT_SECONDARY_BUTTON_CLASS}
                onclick={handleClose}
              >
                Cancel
              </button>
            {/if}

            {#if phase === "error"}
              <button
                type="button"
                class={BLOCKING_ALERT_SECONDARY_BUTTON_CLASS}
                onclick={handleRetry}
              >
                Try again
              </button>
            {/if}

            {#if phase === "form"}
              <PrimaryButton
                class="w-full sm:w-auto border-primary/70 font-mono text-[11px] tracking-[0.18em]"
                isSelected={true}
                disabled={!canSubmit}
                onclick={handleSubmit}
              >
                Import
              </PrimaryButton>
            {:else if phase === "running"}
              <PrimaryButton
                class="w-full sm:w-auto border-primary/70 font-mono text-[11px] tracking-[0.18em] opacity-60"
                isSelected={true}
                disabled={true}
              >
                <CircleNotch weight="regular" class="h-4 w-4 animate-spin" />
                Importing…
              </PrimaryButton>
            {:else if phase === "done"}
              <PrimaryButton
                class="w-full sm:w-auto border-primary/70 font-mono text-[11px] tracking-[0.18em]"
                isSelected={true}
                onclick={handleClose}
              >
                Done
              </PrimaryButton>
            {/if}
          </div>
        </AlertDialog.Content>
      </div>
    </div>
  </AlertDialog.Portal>
</AlertDialog.Root>
