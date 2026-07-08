<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import PrimaryButton from "$components/ui/molecules/PrimaryButton.svelte";
  import { AlertDialog } from "bits-ui";
  import { CircleNotch } from "phosphor-svelte";

  import DoneStep from "./DoneStep.svelte";
  import IntentStep from "./IntentStep.svelte";
  import ProgressStep from "./ProgressStep.svelte";
  import ReviewStep from "./ReviewStep.svelte";
  import SourceStep from "./SourceStep.svelte";
  import WizardStepIndicator from "./WizardStepIndicator.svelte";
  import {
    canAnalyze,
    DEFAULT_FIELDS,
    groupFindings,
    mergeSpec,
    type ImportIntent,
    type WizardFields,
  } from "./wizardUtils";
  import { analyzeImportSource, listIoFormats, startIoImport } from "$lib/api/ioApi";
  import type { ImportPlanResponse, IoFormatResponse } from "$lib/api/restTypes";
  import {
    BLOCKING_ALERT_ACTIONS_CLASS,
    BLOCKING_ALERT_CONTENT_WIDE_CLASS,
    BLOCKING_ALERT_HEADER_CLASS,
    BLOCKING_ALERT_OVERLAY_CLASS,
    BLOCKING_ALERT_SECONDARY_BUTTON_CLASS,
    BLOCKING_ALERT_SUPPORTING_TEXT_CLASS,
    BLOCKING_ALERT_TITLE_CLASS,
    BLOCKING_ALERT_VIEWPORT_CLASS,
  } from "$lib/constants/modalConstants";
  import {
    importJobsStore,
    requestImportJobCancel,
    trackImportJob,
  } from "$lib/stores/importJobsStore.svelte";

  interface Props {
    onClose: () => void;
  }

  let { onClose }: Props = $props();

  type Step = "intent" | "source" | "review" | "progress" | "done";

  const STEP_LABELS = ["Type", "Source", "Review", "Import"];
  const STEP_INDEX: Record<Step, number> = {
    intent: 0,
    source: 1,
    review: 2,
    progress: 3,
    done: 3,
  };

  let open = $state(true);
  let step = $state<Step>("intent");
  let formats = $state<IoFormatResponse[] | null>(null);
  let fields = $state<WizardFields>(structuredClone(DEFAULT_FIELDS));
  let advancedJson = $state("");
  let plan = $state<ImportPlanResponse | null>(null);
  let analyzing = $state(false);
  let analyzeError = $state("");
  let trackedJobId = $state<string | null>(null);
  let errorMessage = $state("");
  let analyzeToken = 0;

  const trackedEntry = $derived(
    trackedJobId
      ? (importJobsStore.value.find((entry) => entry.jobId === trackedJobId) ?? null)
      : null,
  );
  const job = $derived(trackedEntry?.job ?? null);
  const cancelRequested = $derived(trackedEntry?.cancelRequested ?? false);

  const previouslyFocusedElement =
    typeof document !== "undefined" ? (document.activeElement as HTMLElement | null) : null;

  const hasErrors = $derived(plan ? groupFindings(plan).errors.length > 0 : false);
  const canGoAnalyze = $derived(canAnalyze(fields, advancedJson));

  const STEP_META: Record<Step, { title: string; description: string }> = {
    intent: {
      title: "Import Dataset",
      description: "What are you importing?",
    },
    source: {
      title: "Import Dataset",
      description: "Pick the data on your computer and describe it.",
    },
    review: {
      title: "Review the plan",
      description:
        "Analysis runs without writing anything — this is the schema the import creates.",
    },
    progress: {
      title: "Importing…",
      description: "The dataset is built atomically on the server — you can keep using the app.",
    },
    done: { title: "Import Dataset", description: "" },
  };

  $effect(() => {
    if (step === "progress" && job) {
      if (job.status === "done" || job.status === "cancelled") {
        step = "done";
      } else if (job.status === "error" || job.status === "interrupted") {
        errorMessage = job.error?.message || "The import stopped unexpectedly.";
        step = "done";
      }
    }
  });

  $effect(() => {
    if (formats === null) {
      listIoFormats()
        .then((result) => (formats = result))
        .catch(() => (formats = []));
    }
  });

  function handleIntentSelect(intent: ImportIntent) {
    fields.intent = intent;
    step = "source";
  }

  async function runAnalyze() {
    step = "review";
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
    try {
      const started = await startIoImport({
        plan_id: plan?.plan_id,
        source: fields.source.trim(),
        spec: mergeSpec(fields, advancedJson),
      });
      trackedJobId = started.job_id;
      trackImportJob(
        started,
        fields.name.trim() || fields.sourceLabel.trim() || started.dataset || fields.source.trim(),
      );
    } catch (err: unknown) {
      errorMessage = err instanceof Error ? err.message : "Unexpected error starting the import.";
      step = "done";
    }
  }

  function handleRetry() {
    errorMessage = "";
    trackedJobId = null;
    void runAnalyze();
  }

  function handleClose() {
    open = false;
  }

  function handleOpenChange(next: boolean) {
    if (!next) handleClose();
  }

  function handleOpenChangeComplete(next: boolean) {
    if (!next) onClose();
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
          class={BLOCKING_ALERT_CONTENT_WIDE_CLASS}
          trapFocus={true}
          preventScroll={true}
          onEscapeKeydown={(e) => {
            e.preventDefault();
            handleClose();
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

          <WizardStepIndicator steps={STEP_LABELS} current={STEP_INDEX[step]} />

          {#if step === "intent"}
            <IntentStep {formats} onSelect={handleIntentSelect} />
          {:else if step === "source"}
            <SourceStep bind:fields bind:advancedJson />
          {:else if step === "review"}
            <ReviewStep {analyzing} {analyzeError} {plan} />
          {:else if step === "progress"}
            <ProgressStep {job} {cancelRequested} />
          {:else if step === "done"}
            <DoneStep {job} {errorMessage} />
          {/if}

          <div class={BLOCKING_ALERT_ACTIONS_CLASS}>
            {#if step === "intent" || step === "source" || step === "review"}
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
                onclick={() => (step = "intent")}
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
            {:else if step === "review"}
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
                onclick={() => trackedJobId && void requestImportJobCancel(trackedJobId)}
              >
                Cancel import
              </button>
              <PrimaryButton class={primaryClass} isSelected={true} onclick={handleClose}>
                Run in background
              </PrimaryButton>
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
