<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import PrimaryButton from "$components/ui/molecules/PrimaryButton.svelte";
  import { AlertDialog } from "bits-ui";
  import { CircleNotch } from "phosphor-svelte";
  import { onDestroy } from "svelte";

  import AnalyzePreviewStep from "./AnalyzePreviewStep.svelte";
  import DoneStep from "./DoneStep.svelte";
  import FormatPickerStep from "./FormatPickerStep.svelte";
  import ProgressStep from "./ProgressStep.svelte";
  import SourceParamsStep from "./SourceParamsStep.svelte";
  import {
    canAnalyze,
    DEFAULT_FIELDS,
    groupFindings,
    mergeSpec,
    type WizardFields,
  } from "./wizardUtils";
  import { invalidateAll } from "$app/navigation";
  import {
    analyzeImportSource,
    cancelIoJob,
    getIoJob,
    listIoFormats,
    startIoImport,
  } from "$lib/api/ioApi";
  import type { ImportPlanResponse, IoFormatResponse, IoJobResponse } from "$lib/api/restTypes";
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

  let { onClose }: Props = $props();

  type Step = "format" | "source" | "preview" | "progress" | "done";

  let open = $state(true);
  let step = $state<Step>("format");
  let formats = $state<IoFormatResponse[] | null>(null);
  let fields = $state<WizardFields>({ ...DEFAULT_FIELDS });
  let advancedJson = $state("");
  let plan = $state<ImportPlanResponse | null>(null);
  let analyzing = $state(false);
  let analyzeError = $state("");
  let job = $state<IoJobResponse | null>(null);
  let errorMessage = $state("");
  let cancelRequested = $state(false);
  let pollHandle = $state<ReturnType<typeof setInterval> | null>(null);
  let analyzeToken = 0;

  const previouslyFocusedElement =
    typeof document !== "undefined" ? (document.activeElement as HTMLElement | null) : null;

  const running = $derived(step === "progress");
  const hasErrors = $derived(plan ? groupFindings(plan).errors.length > 0 : false);
  const canGoAnalyze = $derived(canAnalyze(fields, advancedJson));

  const STEP_META: Record<Step, { title: string; description: string }> = {
    format: {
      title: "Import Dataset",
      description: "Choose the data format, or let Pixano detect it.",
    },
    source: {
      title: "Import Dataset",
      description: "Point at the source and set the import options.",
    },
    preview: { title: "Review the plan", description: "Analysis runs without writing anything." },
    progress: {
      title: "Importing…",
      description: "The dataset is being built atomically on the server.",
    },
    done: { title: "Import Dataset", description: "" },
  };

  $effect(() => {
    if (formats === null) {
      listIoFormats()
        .then((result) => (formats = result))
        .catch(() => (formats = []));
    }
  });

  function stopPolling() {
    if (pollHandle) {
      clearInterval(pollHandle);
      pollHandle = null;
    }
  }

  onDestroy(stopPolling);

  async function runAnalyze() {
    step = "preview";
    analyzing = true;
    analyzeError = "";
    plan = null;
    const token = ++analyzeToken;
    try {
      const result = await analyzeImportSource(
        fields.source.trim(),
        mergeSpec(fields, advancedJson),
      );
      if (token !== analyzeToken) return;
      plan = result;
    } catch (err: unknown) {
      if (token !== analyzeToken) return;
      analyzeError = err instanceof Error ? err.message : "Unexpected error analyzing the source.";
    } finally {
      if (token === analyzeToken) analyzing = false;
    }
  }

  async function startImport() {
    step = "progress";
    errorMessage = "";
    cancelRequested = false;
    job = null;
    try {
      const started = await startIoImport({
        plan_id: plan?.plan_id,
        source: fields.source.trim(),
        spec: mergeSpec(fields, advancedJson),
      });
      job = started;
      pollHandle = setInterval(async () => {
        if (!job) return;
        try {
          const status = await getIoJob(job.job_id);
          job = status;
          if (status.status === "done" || status.status === "cancelled") {
            stopPolling();
            step = "done";
            await invalidateAll();
          } else if (status.status === "error" || status.status === "interrupted") {
            stopPolling();
            errorMessage = status.error?.message || "The import stopped unexpectedly.";
            step = "done";
          }
        } catch {
          stopPolling();
          errorMessage =
            "Lost connection to the server (the job keeps running; check the jobs list).";
          step = "done";
        }
      }, 2000);
    } catch (err: unknown) {
      errorMessage = err instanceof Error ? err.message : "Unexpected error starting the import.";
      step = "done";
    }
  }

  async function requestCancel() {
    if (!job || cancelRequested) return;
    cancelRequested = true;
    try {
      await cancelIoJob(job.job_id);
    } catch {
      cancelRequested = false;
    }
  }

  function handleRetry() {
    errorMessage = "";
    job = null;
    void runAnalyze();
  }

  function handleClose() {
    stopPolling();
    open = false;
  }

  function handleOpenChange(next: boolean) {
    if (!next && running) return;
    if (!next) handleClose();
  }

  function handleOpenChangeComplete(next: boolean) {
    if (!next) {
      stopPolling();
      onClose();
    }
  }

  function handleCloseAutoFocus(event: Event) {
    event.preventDefault();
    if (previouslyFocusedElement && previouslyFocusedElement.isConnected) {
      previouslyFocusedElement.focus({ preventScroll: true });
    }
  }

  const primaryClass = "w-full sm:w-auto border-primary/70 font-mono text-[11px] tracking-[0.18em]";
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
            e.preventDefault();
            if (!running) handleClose();
          }}
          onCloseAutoFocus={handleCloseAutoFocus}
        >
          <div class="pointer-events-none absolute inset-x-0 top-0 h-px bg-primary/15"></div>

          <div class={BLOCKING_ALERT_HEADER_CLASS}>
            <AlertDialog.Title class={BLOCKING_ALERT_TITLE_CLASS}>
              {STEP_META[step].title}
            </AlertDialog.Title>
            {#if STEP_META[step].description}
              <AlertDialog.Description class={BLOCKING_ALERT_SUPPORTING_TEXT_CLASS}>
                <p>{STEP_META[step].description}</p>
              </AlertDialog.Description>
            {/if}
          </div>

          {#if step === "format"}
            <FormatPickerStep
              {formats}
              selected={fields.format}
              onSelect={(format: string) => {
                fields.format = format;
                step = "source";
              }}
            />
          {:else if step === "source"}
            <SourceParamsStep bind:fields bind:advancedJson />
          {:else if step === "preview"}
            <AnalyzePreviewStep {analyzing} {analyzeError} {plan} />
          {:else if step === "progress"}
            <ProgressStep {job} {cancelRequested} />
          {:else if step === "done"}
            <DoneStep {job} {errorMessage} />
          {/if}

          <div class={BLOCKING_ALERT_ACTIONS_CLASS}>
            {#if step === "format" || step === "source" || step === "preview"}
              <button
                type="button"
                class={BLOCKING_ALERT_SECONDARY_BUTTON_CLASS}
                onclick={handleClose}
              >
                Cancel
              </button>
            {/if}

            {#if step === "source"}
              <button
                type="button"
                class={BLOCKING_ALERT_SECONDARY_BUTTON_CLASS}
                onclick={() => (step = "format")}
              >
                Back
              </button>
              <PrimaryButton
                class={primaryClass}
                isSelected={true}
                disabled={!canGoAnalyze}
                onclick={runAnalyze}
              >
                Analyze
              </PrimaryButton>
            {:else if step === "preview"}
              <button
                type="button"
                class={BLOCKING_ALERT_SECONDARY_BUTTON_CLASS}
                onclick={() => (step = "source")}
              >
                Back
              </button>
              <PrimaryButton
                class={primaryClass}
                isSelected={true}
                disabled={analyzing || !!analyzeError || !plan || hasErrors}
                onclick={startImport}
              >
                {#if analyzing}
                  <CircleNotch weight="regular" class="h-4 w-4 animate-spin" />
                {/if}
                Start import
              </PrimaryButton>
            {:else if step === "progress"}
              <button
                type="button"
                class={BLOCKING_ALERT_SECONDARY_BUTTON_CLASS}
                disabled={cancelRequested || !job}
                onclick={requestCancel}
              >
                Cancel import
              </button>
            {:else if step === "done"}
              {#if errorMessage}
                <button
                  type="button"
                  class={BLOCKING_ALERT_SECONDARY_BUTTON_CLASS}
                  onclick={handleRetry}
                >
                  Try again
                </button>
              {/if}
              <PrimaryButton class={primaryClass} isSelected={true} onclick={handleClose}>
                Done
              </PrimaryButton>
            {/if}
          </div>
        </AlertDialog.Content>
      </div>
    </div>
  </AlertDialog.Portal>
</AlertDialog.Root>
