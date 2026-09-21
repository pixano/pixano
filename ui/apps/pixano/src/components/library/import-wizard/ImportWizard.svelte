<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { AlertDialog } from "bits-ui";
  import {
    ArrowRight,
    CheckCircle,
    CircleNotch,
    Database,
    Info,
    SlidersHorizontal,
    UploadSimple,
    VideoCamera,
    X,
  } from "phosphor-svelte";
  import { onDestroy, tick } from "svelte";

  import IntentStep from "./IntentStep.svelte";
  import type { RawTask } from "./layoutPreflight";
  import LerobotSchemaBuilder from "./LerobotSchemaBuilder.svelte";
  import { DEFAULT_ANNOTATIONS } from "./rawSchema";
  import RawSchemaBuilder from "./RawSchemaBuilder.svelte";
  import RawTaskStep from "./RawTaskStep.svelte";
  import ReviewStep from "./ReviewStep.svelte";
  import { createWizardSourceState } from "./sourceState";
  import SourceStep from "./SourceStep.svelte";
  import WizardStepIndicator from "./WizardStepIndicator.svelte";
  import {
    WIZARD_DISCLOSURE_CLASS,
    WIZARD_DISCLOSURE_SUMMARY_CLASS,
    WIZARD_GHOST_BUTTON_CLASS,
    WIZARD_ICON_BUTTON_CLASS,
    WIZARD_PRIMARY_BUTTON_CLASS,
    WIZARD_SECONDARY_BUTTON_CLASS,
  } from "./wizardStyles";
  import {
    DEFAULT_FIELDS,
    groupFindings,
    mergeSpec,
    parseAdvancedSpec,
    setupValidationMessage,
    showsLerobotFields,
    type ImportIntent,
    type WizardFields,
  } from "./wizardUtils";
  import { analyzeImportSource, listIoFormats, startIoImport } from "$lib/api/ioApi";
  import type { ImportPlanResponse, IoFormatResponse } from "$lib/api/restTypes";
  import { BLOCKING_ALERT_OVERLAY_CLASS } from "$lib/constants/modalConstants";
  import { trackImportJob } from "$lib/stores/importJobsStore.svelte";

  interface Props {
    onClose: () => void;
  }
  let { onClose }: Props = $props();

  let open = $state(true);
  let step = $state<"setup" | "review">("setup");
  let selectedIntent = $state<ImportIntent | null>(null);
  let formats = $state<IoFormatResponse[] | null>(null);
  let fields = $state<WizardFields>(structuredClone(DEFAULT_FIELDS));
  let sourceState = $state(createWizardSourceState());
  let sourceStep = $state<{ resetSource: (mode?: "upload" | "hub") => void } | null>(null);
  let bodyElement = $state<HTMLDivElement | null>(null);
  let setupElement = $state<HTMLDivElement | null>(null);
  let sourcePane = $state<HTMLElement | null>(null);
  let annotationPane = $state<HTMLElement | null>(null);
  let reviewElement = $state<HTMLDivElement | null>(null);
  let sourceNotice = $state("");
  let lastSetupFocus: HTMLElement | null = null;
  let setupScroll = { body: 0, source: 0, annotation: 0, desktop: false };
  let advancedJson = $state("");
  let plan = $state<ImportPlanResponse | null>(null);
  let analyzing = $state(false);
  let analyzeError = $state("");
  let starting = $state(false);
  let startError = $state("");
  let analyzeToken = 0;

  const previouslyFocusedElement =
    typeof document !== "undefined" ? (document.activeElement as HTMLElement | null) : null;
  const hasErrors = $derived(plan ? groupFindings(plan).errors.length > 0 : false);
  const setupMessage = $derived(
    !selectedIntent
      ? "Select a data format."
      : sourceState.status === "uploading"
        ? "Uploading source. Annotation setup remains available."
        : setupValidationMessage(fields, advancedJson),
  );
  const canGoAnalyze = $derived(selectedIntent !== null && !setupMessage);
  const isRaw = $derived(selectedIntent === "raw");
  const showLerobot = $derived(selectedIntent !== null && showsLerobotFields(fields));
  const advancedError = $derived(parseAdvancedSpec(advancedJson).error);
  const referenceMode = $derived(
    Object.values(plan?.inferred_schema?.views ?? {}).some((view) => view.base === "Video"),
  );
  const schemaSummary = $derived.by(() => {
    const schema = isRaw ? fields.raw : showLerobot ? fields.lerobot : null;
    if (!schema) return "Source schema available in Review.";
    const count = schema.entityAttrs.length;
    return `${count} object attribute${count === 1 ? "" : "s"} configured`;
  });

  $effect(() => {
    if (formats === null)
      listIoFormats()
        .then((result) => (formats = result))
        .catch(() => (formats = []));
  });
  onDestroy(() => {
    analyzeToken++;
  });

  function invalidatePlan() {
    analyzeToken++;
    analyzing = false;
    plan = null;
    analyzeError = "";
    startError = "";
  }

  function handleIntentSelect(intent: ImportIntent) {
    if (selectedIntent === intent) return;
    sourceStep?.resetSource(intent === "lerobot" ? "hub" : "upload");
    sourceState.mode = intent === "lerobot" ? "hub" : "upload";
    fields.intent = intent;
    selectedIntent = intent;
    invalidatePlan();
  }

  function handleTaskSelect(task: RawTask) {
    if (fields.raw.task === task) return;
    const hadSource = !!fields.source || sourceState.status === "uploading";
    sourceStep?.resetSource("upload");
    if (hadSource) sourceNotice = "Task changed. Select a folder with the required layout.";
    fields.raw.task = task;
    fields.raw.annotations = [...DEFAULT_ANNOTATIONS[task]];
    invalidatePlan();
  }

  async function focusReview() {
    await tick();
    reviewElement?.scrollTo({ top: 0 });
    reviewElement?.focus({ preventScroll: true });
  }

  function focusSection(id: "import-source" | "import-annotations") {
    const pane = id === "import-source" ? sourcePane : annotationPane;
    if (!pane || !setupElement) return;
    if (window.matchMedia("(min-width: 1024px)").matches) pane.scrollTo({ top: 0 });
    else
      setupElement.scrollTo({
        top:
          setupElement.scrollTop +
          pane.getBoundingClientRect().top -
          setupElement.getBoundingClientRect().top,
      });
    pane.querySelector<HTMLElement>("h2")?.focus({ preventScroll: true });
  }

  function focusTask() {
    focusSection("import-annotations");
    annotationPane
      ?.querySelector<HTMLElement>('#import-task button[aria-pressed="true"]')
      ?.focus({ preventScroll: true });
  }

  async function runAnalyze() {
    if (!canGoAnalyze || analyzing) return;
    setupScroll = {
      body: setupElement?.scrollTop ?? 0,
      source: sourcePane?.scrollTop ?? 0,
      annotation: annotationPane?.scrollTop ?? 0,
      desktop: window.matchMedia("(min-width: 1024px)").matches,
    };
    step = "review";
    analyzing = true;
    analyzeError = "";
    startError = "";
    plan = null;
    void focusReview();
    const token = ++analyzeToken;
    try {
      const result = await analyzeImportSource(
        fields.source.trim(),
        mergeSpec(fields, advancedJson),
      );
      if (token === analyzeToken) plan = result;
    } catch (err: unknown) {
      if (token === analyzeToken)
        analyzeError =
          err instanceof Error ? err.message : "Unexpected error analyzing the source.";
    } finally {
      if (token === analyzeToken) analyzing = false;
    }
  }

  async function editSetup() {
    invalidatePlan();
    step = "setup";
    await tick();
    setupElement?.scrollTo({ top: setupScroll.body });
    sourcePane?.scrollTo({ top: setupScroll.source });
    annotationPane?.scrollTo({ top: setupScroll.annotation });
    if (lastSetupFocus?.isConnected) {
      lastSetupFocus.focus({ preventScroll: true });
      if (setupScroll.desktop !== window.matchMedia("(min-width: 1024px)").matches)
        lastSetupFocus.scrollIntoView({ block: "nearest" });
    } else bodyElement?.focus({ preventScroll: true });
  }

  async function startImport() {
    if (starting || analyzing || !plan || analyzeError || hasErrors) return;
    starting = true;
    startError = "";
    try {
      const started = await startIoImport({
        plan_id: plan.plan_id,
        source: fields.source.trim(),
        spec: mergeSpec(fields, advancedJson),
      });
      trackImportJob(
        started,
        fields.name.trim() || fields.sourceLabel.trim() || started.dataset || fields.source.trim(),
      );
      open = false;
    } catch (err: unknown) {
      startError = err instanceof Error ? err.message : "Unexpected error starting the import.";
    } finally {
      starting = false;
    }
  }

  function handleClose() {
    if (!starting) open = false;
  }
  function handleCloseAutoFocus(event: Event) {
    event.preventDefault();
    if (previouslyFocusedElement?.isConnected)
      previouslyFocusedElement.focus({ preventScroll: true });
  }
</script>

<AlertDialog.Root
  {open}
  onOpenChange={(next) => {
    if (!next) handleClose();
  }}
  onOpenChangeComplete={(next) => {
    if (!next) onClose();
  }}
>
  <AlertDialog.Portal>
    <AlertDialog.Overlay class={BLOCKING_ALERT_OVERLAY_CLASS} />
    <div class="wizard-viewport">
      <AlertDialog.Content
        class="wizard-shell"
        trapFocus={true}
        preventScroll={true}
        onEscapeKeydown={(event) => {
          event.preventDefault();
          handleClose();
        }}
        onCloseAutoFocus={handleCloseAutoFocus}
      >
        <header class="wizard-header">
          <div class="wizard-title-group">
            <span class="wizard-title-icon"><UploadSimple size={22} weight="regular" /></span>
            <div>
              <AlertDialog.Title class="wizard-title">
                {step === "setup" ? "Import dataset" : "Review import"}
              </AlertDialog.Title>
              <AlertDialog.Description class="wizard-description">
                {step === "setup"
                  ? "Configure source and annotation schema."
                  : "Validate the import plan and schema."}
              </AlertDialog.Description>
            </div>
          </div>
          <div class="wizard-header-actions">
            <div class="wizard-steps">
              <WizardStepIndicator steps={["Setup", "Review"]} current={step === "setup" ? 0 : 1} />
            </div>
            <button
              type="button"
              class={WIZARD_ICON_BUTTON_CLASS}
              aria-label="Close import wizard"
              disabled={starting}
              onclick={handleClose}
            >
              <X size={18} />
            </button>
          </div>
        </header>
        {#if step === "setup"}
          <nav class="wizard-section-nav" aria-label="Setup sections">
            <button type="button" onclick={() => focusSection("import-source")}>
              <Database size={16} />Source
            </button>
            <button type="button" onclick={() => focusSection("import-annotations")}>
              <SlidersHorizontal size={16} />Annotation setup
            </button>
          </nav>
        {/if}
        <div
          class="wizard-body"
          bind:this={bodyElement}
          tabindex="-1"
          role="region"
          aria-label={step === "setup" ? "Import setup" : "Import review"}
        >
          <!-- Mounted through Review to retain uploads, editing state, and both scroll positions. -->
          <div
            class="wizard-setup"
            class:is-hidden={step !== "setup"}
            bind:this={setupElement}
            onfocusin={(event) => {
              if (event.target instanceof HTMLElement) lastSetupFocus = event.target;
            }}
          >
            <section
              id="import-source"
              class="wizard-pane wizard-source"
              aria-labelledby="import-source-title"
              bind:this={sourcePane}
            >
              <div class="wizard-pane-heading">
                <h2 id="import-source-title" tabindex="-1">Source</h2>
                <p>Select the format and data location.</p>
              </div>
              <IntentStep {formats} selected={selectedIntent} onSelect={handleIntentSelect} />
              {#if selectedIntent}
                <SourceStep
                  bind:this={sourceStep}
                  bind:fields
                  bind:sourceState
                  bind:notice={sourceNotice}
                  onChangeTask={focusTask}
                />
              {:else}
                <div class="source-placeholder">
                  <UploadSimple size={20} />
                  <p>Select a format to configure the source.</p>
                </div>
              {/if}
            </section>
            <section
              id="import-annotations"
              class="wizard-pane wizard-annotations"
              aria-labelledby="import-annotations-title"
              bind:this={annotationPane}
            >
              <div class="wizard-pane-heading">
                <h2 id="import-annotations-title" tabindex="-1">Annotation setup</h2>
                <p>Configure annotation tools and object attributes.</p>
              </div>
              {#if !selectedIntent}
                <div class="annotation-placeholder">
                  <div class="schema-illustration" aria-hidden="true">
                    <div class="illustration-frame">
                      <span class="illustration-object"></span>
                      <span class="illustration-label">object</span>
                    </div>
                    <div class="illustration-attributes">
                      <span></span>
                      <span></span>
                      <span></span>
                    </div>
                  </div>
                  <h3>Annotation schema</h3>
                  <p>Select a format to configure annotation tools and attributes.</p>
                  <span class="annotation-placeholder-note">
                    Existing dataset schemas are preserved.
                  </span>
                </div>
              {:else if isRaw}
                <div id="import-task">
                  <RawTaskStep selected={fields.raw.task} onSelect={handleTaskSelect} />
                </div>
                <RawSchemaBuilder bind:raw={fields.raw} />
              {:else if showLerobot}
                <div class="included-task" aria-label="Annotation task">
                  <span class="included-task-icon"><VideoCamera size={24} /></span>
                  <div>
                    <h3>Video annotation</h3>
                    <p>Object annotations and tracks across episode frames.</p>
                  </div>
                  <span class="included-task-badge">LeRobot</span>
                </div>
                <LerobotSchemaBuilder bind:schema={fields.lerobot} />
              {:else}
                <div class="imported-schema">
                  <span class="included-task-icon"><Database size={24} /></span>
                  <div>
                    <h3>
                      {selectedIntent === "auto" ? "Inferred schema" : "Source schema"}
                    </h3>
                    <p>
                      {selectedIntent === "coco"
                        ? "COCO categories map to object attributes; annotations are retained."
                        : selectedIntent === "pixano_jsonl"
                          ? "Views, object attributes, and annotations are preserved."
                          : "The format and schema are detected from the source. Select Raw media for unannotated images or videos."}
                    </p>
                    <p class="imported-schema-next">
                      <CheckCircle size={16} />Review shows the resolved schema.
                    </p>
                  </div>
                </div>
              {/if}
              {#if selectedIntent}
                <details class={WIZARD_DISCLOSURE_CLASS} open={!!advancedError}>
                  <summary class={WIZARD_DISCLOSURE_SUMMARY_CLASS}>
                    Advanced JSON{#if advancedJson.trim()}<span class="override-badge">
                        Overrides active
                      </span>{/if}
                  </summary>
                  <div class="advanced-content">
                    <p>
                      Import-spec overrides take precedence over form values. Review shows the
                      resolved schema.
                    </p>
                    <label for="wizard-advanced" class="sr-only">Advanced import spec JSON</label>
                    <textarea
                      id="wizard-advanced"
                      class="advanced-editor"
                      placeholder={'{\n  "schema": {"record": {"attrs": {"weather": "str"}}}\n}'}
                      bind:value={advancedJson}
                      aria-invalid={!!advancedError}
                      aria-describedby={advancedError ? "wizard-advanced-error" : undefined}
                    ></textarea>
                    {#if advancedError}<p
                        id="wizard-advanced-error"
                        class="text-destructive"
                        role="alert"
                      >
                        {advancedError}
                      </p>{/if}
                  </div>
                </details>
              {/if}
            </section>
          </div>
          {#if step === "review"}
            <div
              class="wizard-review"
              bind:this={reviewElement}
              tabindex="-1"
              role="region"
              aria-label="Reviewed import plan"
            >
              <ReviewStep
                {analyzing}
                {analyzeError}
                {plan}
                {referenceMode}
                datasetName={fields.name.trim() || fields.sourceLabel.trim()}
                sourceLabel={fields.sourceLabel ||
                  (sourceState.mode === "hub" ? fields.source.trim() : "")}
              />
              {#if startError}<div class="start-error" role="alert">
                  <p class="font-medium">Import failed to start</p>
                  <p class="mt-1 whitespace-pre-wrap">{startError}</p>
                </div>{/if}
            </div>
          {/if}
        </div>
        <footer class="wizard-footer">
          <div class="wizard-status" aria-live="polite">
            {#if step === "setup" && canGoAnalyze}<CheckCircle
                size={16}
                class="shrink-0 text-primary"
              />{:else}<Info size={16} class="shrink-0" />{/if}
            <p>
              {step === "setup"
                ? setupMessage || schemaSummary
                : analyzing
                  ? "Analyzing source…"
                  : hasErrors || analyzeError
                    ? "Resolve validation errors in setup."
                    : "Import runs in the background."}
            </p>
          </div>
          <div class="wizard-footer-actions">
            <button
              type="button"
              class={WIZARD_GHOST_BUTTON_CLASS}
              disabled={starting}
              onclick={handleClose}
            >
              Cancel
            </button>
            {#if step === "setup"}<button
                type="button"
                class={WIZARD_PRIMARY_BUTTON_CLASS}
                disabled={!canGoAnalyze}
                onclick={runAnalyze}
              >
                Review import<ArrowRight size={16} />
              </button>
            {:else}<button
                type="button"
                class={WIZARD_SECONDARY_BUTTON_CLASS}
                disabled={starting}
                onclick={() => void editSetup()}
              >
                Edit setup
              </button>
              <button
                type="button"
                class={WIZARD_PRIMARY_BUTTON_CLASS}
                disabled={starting || analyzing || !!analyzeError || !plan || hasErrors}
                onclick={startImport}
              >
                {#if starting}<CircleNotch size={16} class="animate-spin" />Starting…{:else}Start
                  import<ArrowRight size={16} />{/if}
              </button>{/if}
          </div>
        </footer>
      </AlertDialog.Content>
    </div>
  </AlertDialog.Portal>
</AlertDialog.Root>

<style>
  .wizard-viewport {
    position: fixed;
    inset: 0;
    z-index: 201;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 24px;
  }
  :global(.wizard-shell) {
    position: relative;
    display: flex;
    flex-direction: column;
    width: 100%;
    max-width: 1440px;
    height: calc(100dvh - 48px);
    overflow: hidden;
    border: 1px solid color-mix(in srgb, var(--color-border) 75%, transparent);
    border-radius: 20px;
    background: color-mix(in srgb, var(--color-card) 94%, transparent);
    color: var(--color-foreground);
    backdrop-filter: blur(24px);
    box-shadow:
      var(--shadow-elevation-3),
      inset 0 1px 0 color-mix(in srgb, var(--color-card) 60%, transparent);
    text-align: left;
  }
  .wizard-header,
  .wizard-footer {
    display: flex;
    flex-shrink: 0;
    align-items: center;
    justify-content: space-between;
    gap: 24px;
    padding: 18px 28px;
  }
  .wizard-header {
    border-bottom: 1px solid color-mix(in srgb, var(--color-border) 65%, transparent);
  }
  .wizard-title-group,
  .wizard-header-actions {
    display: flex;
    align-items: center;
    gap: 16px;
    min-width: 0;
  }
  .wizard-title-icon {
    display: grid;
    width: 42px;
    height: 42px;
    flex-shrink: 0;
    place-items: center;
    border-radius: 12px;
    color: var(--color-primary);
    background: color-mix(in srgb, var(--color-primary) 8%, transparent);
    box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--color-primary) 8%, transparent);
  }
  :global(.wizard-title) {
    font-size: 19px;
    line-height: 26px;
    font-weight: 600;
    letter-spacing: -0.025em;
  }
  :global(.wizard-description) {
    margin-top: 2px;
    color: var(--color-muted-foreground);
    font-size: 13px;
    line-height: 20px;
  }
  .wizard-body {
    flex: 1;
    min-height: 0;
    overflow: hidden;
    outline: none;
  }
  .wizard-setup {
    display: grid;
    grid-template-columns: minmax(0, 2fr) minmax(0, 3fr);
    height: 100%;
    min-height: 0;
  }
  .wizard-setup.is-hidden {
    display: none;
  }
  .wizard-pane {
    min-width: 0;
    min-height: 0;
    overflow-y: auto;
    overscroll-behavior-y: contain;
    padding: 24px 28px 28px;
    scrollbar-width: thin;
    scrollbar-color: color-mix(in srgb, var(--color-muted-foreground) 30%, transparent) transparent;
  }
  .wizard-pane > :global(* + *) {
    margin-top: 24px;
  }
  .wizard-source {
    background: color-mix(in srgb, var(--color-surface-2) 65%, transparent);
    border-right: 1px solid color-mix(in srgb, var(--color-border) 65%, transparent);
  }
  .wizard-annotations {
    background: color-mix(in srgb, var(--color-card) 80%, transparent);
  }
  .wizard-pane-heading h2 {
    font-size: 17px;
    line-height: 24px;
    font-weight: 600;
    letter-spacing: -0.02em;
    outline: none;
  }
  .wizard-pane-heading p {
    margin-top: 4px;
    color: var(--color-muted-foreground);
    font-size: 13px;
    line-height: 20px;
  }
  .source-placeholder {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 20px 0;
    border-top: 1px solid var(--color-border);
    color: var(--color-muted-foreground);
    font-size: 13px;
  }
  .annotation-placeholder {
    display: flex;
    align-items: center;
    flex-direction: column;
    justify-content: center;
    min-height: 340px;
    padding: 40px 24px;
    text-align: center;
  }
  .annotation-placeholder h3 {
    margin-top: 24px;
    font-size: 17px;
    font-weight: 600;
    letter-spacing: -0.02em;
  }
  .annotation-placeholder p {
    max-width: 330px;
    margin-top: 10px;
    font-size: 14px;
    line-height: 22px;
    color: var(--color-muted-foreground);
  }
  .annotation-placeholder-note {
    margin-top: 20px;
    font-size: 12px;
    color: var(--color-muted-foreground);
  }
  .schema-illustration {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 16px;
    border: 1px solid var(--color-border);
    border-radius: 16px;
    background: var(--color-surface-2);
    box-shadow: var(--shadow-elevation-1);
  }
  .illustration-frame {
    position: relative;
    width: 90px;
    height: 70px;
    border-radius: 8px;
    border: 1px solid var(--color-border);
    background: var(--color-card);
  }
  .illustration-object {
    position: absolute;
    top: 22px;
    left: 26px;
    width: 38px;
    height: 32px;
    border: 1px solid color-mix(in srgb, var(--color-primary) 60%, transparent);
    border-radius: 4px;
    background: color-mix(in srgb, var(--color-primary) 8%, transparent);
  }
  .illustration-label {
    position: absolute;
    top: 10px;
    left: 26px;
    color: var(--color-primary);
    font-size: 9px;
  }
  .illustration-attributes {
    display: grid;
    gap: 8px;
    width: 68px;
  }
  .illustration-attributes span {
    height: 8px;
    border-radius: 3px;
    background: var(--color-border);
  }
  .illustration-attributes span:nth-child(2) {
    width: 80%;
  }
  .illustration-attributes span:nth-child(3) {
    width: 60%;
  }
  .included-task,
  .imported-schema {
    display: flex;
    align-items: center;
    gap: 14px;
    padding: 16px;
    border: 1px solid color-mix(in srgb, var(--color-border) 75%, transparent);
    border-radius: 12px;
    background: color-mix(in srgb, var(--color-surface-2) 65%, transparent);
  }
  .included-task {
    display: grid;
    grid-template-columns: 42px minmax(0, 1fr) auto;
  }
  .included-task-icon {
    display: grid;
    place-items: center;
    flex-shrink: 0;
    width: 42px;
    height: 42px;
    border-radius: 10px;
    color: var(--color-primary);
    background: color-mix(in srgb, var(--color-primary) 7%, transparent);
  }
  .included-task h3,
  .imported-schema h3 {
    font-size: 14px;
    font-weight: 600;
  }
  .included-task p,
  .imported-schema p {
    margin-top: 4px;
    font-size: 12px;
    line-height: 19px;
    color: var(--color-muted-foreground);
  }
  .included-task-badge {
    margin-left: auto;
    flex-shrink: 0;
    color: var(--color-muted-foreground);
    border: 1px solid var(--color-border);
    border-radius: 5px;
    padding: 3px 7px;
    font-size: 11px;
  }
  .imported-schema {
    align-items: flex-start;
  }
  .imported-schema .imported-schema-next {
    display: flex;
    gap: 6px;
    align-items: center;
    margin-top: 16px;
  }
  .override-badge {
    margin-left: 8px;
    color: var(--color-primary);
    font-size: 11px;
    font-weight: 500;
  }
  .advanced-content {
    display: grid;
    gap: 12px;
    margin-top: 16px;
    color: var(--color-muted-foreground);
    font-size: 12px;
    line-height: 19px;
  }
  .advanced-editor {
    width: 100%;
    height: 150px;
    resize: vertical;
    border: 1px solid var(--color-border);
    border-radius: 10px;
    padding: 12px;
    background: var(--color-surface-2);
    color: var(--color-foreground);
    font-family: var(--font-mono);
    font-size: 12px;
  }
  .advanced-editor:focus-visible {
    outline: 2px solid var(--color-ring);
    outline-offset: 2px;
  }
  .wizard-review {
    height: 100%;
    overflow-y: auto;
    overscroll-behavior-y: contain;
    padding: 28px 0;
    outline: none;
  }
  .start-error {
    margin: 20px 28px 0;
    padding: 16px;
    border-radius: 12px;
    border: 1px solid color-mix(in srgb, var(--color-destructive) 40%, transparent);
    background: color-mix(in srgb, var(--color-destructive) 5%, transparent);
    color: var(--color-destructive);
    font-size: 13px;
  }
  .wizard-footer {
    border-top: 1px solid color-mix(in srgb, var(--color-border) 65%, transparent);
    padding-top: 14px;
    padding-bottom: 14px;
  }
  .wizard-status {
    display: flex;
    align-items: center;
    gap: 8px;
    min-width: 0;
    font-size: 12px;
    line-height: 18px;
    color: var(--color-muted-foreground);
  }
  .wizard-footer-actions {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-shrink: 0;
  }
  .wizard-section-nav {
    display: none;
  }
  @media (max-width: 1023px) {
    .wizard-setup {
      display: block;
      overflow-y: auto;
      overscroll-behavior-y: contain;
    }
    .wizard-setup.is-hidden {
      display: none;
    }
    .wizard-pane {
      overflow: visible;
      height: auto;
    }
    .wizard-source {
      border-right: 0;
      border-bottom: 1px solid var(--color-border);
    }
    .wizard-section-nav {
      display: flex;
      gap: 8px;
      flex-shrink: 0;
      padding: 8px 20px;
      border-bottom: 1px solid var(--color-border);
    }
    .wizard-section-nav button {
      display: flex;
      align-items: center;
      gap: 8px;
      border-radius: 8px;
      padding: 8px 12px;
      color: var(--color-muted-foreground);
      font-size: 13px;
      font-weight: 500;
    }
    .wizard-section-nav button:hover,
    .wizard-section-nav button:focus-visible {
      color: var(--color-primary);
      background: color-mix(in srgb, var(--color-primary) 7%, transparent);
    }
  }
  @media (max-width: 639px) {
    .wizard-viewport {
      padding: 0;
    }
    :global(.wizard-shell) {
      height: 100dvh;
      border-radius: 0;
    }
    .wizard-header {
      padding: 16px 20px;
      gap: 12px;
    }
    .wizard-title-icon,
    .wizard-steps {
      display: none;
    }
    .wizard-pane {
      padding: 20px;
    }
    .wizard-footer {
      flex-wrap: wrap;
      gap: 10px;
      padding: 12px 20px;
    }
    .wizard-footer-actions {
      justify-content: flex-end;
      width: 100%;
      flex-wrap: wrap;
    }
    .included-task {
      grid-template-columns: 42px minmax(0, 1fr);
    }
    .included-task-badge {
      grid-column: 2;
      margin-left: 0;
      justify-self: start;
    }
    .annotation-placeholder {
      min-height: 280px;
      padding: 24px 8px;
    }
  }
</style>
