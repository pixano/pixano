<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import PrimaryButton from "$components/ui/molecules/PrimaryButton.svelte";
  import { AlertDialog } from "bits-ui";
  import { CircleNotch } from "phosphor-svelte";

  import {
    BLOCKING_ALERT_ACTIONS_CLASS,
    BLOCKING_ALERT_CONTENT_CLASS,
    BLOCKING_ALERT_HEADER_CLASS,
    BLOCKING_ALERT_OVERLAY_CLASS,
    BLOCKING_ALERT_SECONDARY_BUTTON_CLASS,
    BLOCKING_ALERT_STATUS_CLASS,
    BLOCKING_ALERT_STATUS_DANGER_CLASS,
    BLOCKING_ALERT_STATUS_NEUTRAL_CLASS,
    BLOCKING_ALERT_SUPPORTING_TEXT_CLASS,
    BLOCKING_ALERT_TITLE_CLASS,
    BLOCKING_ALERT_VIEWPORT_CLASS,
  } from "$lib/constants/modalConstants";

  type BlockingAlertAction = "confirm" | "cancel" | "alternative";
  type BlockingAlertTone = "neutral" | "danger";

  interface Props {
    title: string;
    supportingText?: string[];
    confirmLabel?: string;
    cancelLabel?: string;
    alternativeLabel?: string;
    escapeAction?: BlockingAlertAction;
    confirmDisabled?: boolean;
    cancelDisabled?: boolean;
    alternativeDisabled?: boolean;
    statusMessage?: string;
    statusTone?: BlockingAlertTone;
    isBusy?: boolean;
    onConfirm?: () => void;
    onCancel?: () => void;
    onAlternative?: () => void;
  }

  let {
    title,
    supportingText = [],
    confirmLabel = "OK",
    cancelLabel = "",
    alternativeLabel = "",
    escapeAction = "cancel",
    confirmDisabled = false,
    cancelDisabled = false,
    alternativeDisabled = false,
    statusMessage = "",
    statusTone = "neutral",
    isBusy = false,
    onConfirm,
    onCancel,
    onAlternative,
  }: Props = $props();

  let open = $state(true);
  let pendingAction = $state<BlockingAlertAction | null>(null);
  let previouslyFocusedElement: HTMLElement | null =
    typeof document !== "undefined" && document.activeElement instanceof HTMLElement
      ? document.activeElement
      : null;

  const normalizedSupportingText = $derived(
    supportingText.filter((line) => typeof line === "string" && line.trim().length > 0),
  );
  const allActionsDisabled = $derived(confirmDisabled && cancelDisabled && alternativeDisabled);

  function isActionDisabled(action: BlockingAlertAction) {
    switch (action) {
      case "confirm":
        return confirmDisabled;
      case "alternative":
        return alternativeDisabled;
      case "cancel":
        return cancelDisabled;
    }
  }

  function beginClose(action: BlockingAlertAction) {
    if (!open || isActionDisabled(action)) return;
    pendingAction = action;
    open = false;
  }

  function handleOpenChange(nextOpen: boolean) {
    if (!nextOpen && allActionsDisabled) {
      open = true;
      return;
    }

    open = nextOpen;
    if (!nextOpen && pendingAction === null) {
      pendingAction = escapeAction;
    }
  }

  function handleEscapeKeydown(event: KeyboardEvent) {
    event.preventDefault();
    if (isActionDisabled(escapeAction)) return;
    beginClose(escapeAction);
  }

  function handleContentKeydown(event: KeyboardEvent) {
    if (event.key !== "Enter") return;
    event.preventDefault();
    event.stopPropagation();
    if (confirmDisabled) return;
    beginClose("confirm");
  }

  function handleCloseAutoFocus(event: Event) {
    event.preventDefault();
    if (previouslyFocusedElement && previouslyFocusedElement.isConnected) {
      previouslyFocusedElement.focus({ preventScroll: true });
    }
  }

  function invokePendingAction(action: BlockingAlertAction | null) {
    switch (action) {
      case "confirm":
        onConfirm?.();
        return;
      case "alternative":
        onAlternative?.();
        return;
      case "cancel":
        onCancel?.();
        return;
      default:
        return;
    }
  }

  function handleOpenChangeComplete(nextOpen: boolean) {
    if (nextOpen) return;
    const action = pendingAction;
    pendingAction = null;
    invokePendingAction(action);
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
          onEscapeKeydown={handleEscapeKeydown}
          onCloseAutoFocus={handleCloseAutoFocus}
          onkeydown={handleContentKeydown}
        >
          <div class="pointer-events-none absolute inset-x-0 top-0 h-px bg-primary/15"></div>

          <div class={BLOCKING_ALERT_HEADER_CLASS}>
            <AlertDialog.Title class={BLOCKING_ALERT_TITLE_CLASS}>
              {title}
            </AlertDialog.Title>

            {#if normalizedSupportingText.length > 0}
              <AlertDialog.Description class={BLOCKING_ALERT_SUPPORTING_TEXT_CLASS}>
                {#each normalizedSupportingText as line}
                  <p>{line}</p>
                {/each}
              </AlertDialog.Description>
            {/if}

            {#if statusMessage}
              <div
                class={`${BLOCKING_ALERT_STATUS_CLASS} ${
                  statusTone === "danger"
                    ? BLOCKING_ALERT_STATUS_DANGER_CLASS
                    : BLOCKING_ALERT_STATUS_NEUTRAL_CLASS
                }`}
              >
                {#if isBusy}
                  <CircleNotch weight="regular" class="h-4 w-4 shrink-0 animate-spin" />
                {/if}
                <span>{statusMessage}</span>
              </div>
            {/if}
          </div>

          {#if cancelLabel || alternativeLabel || confirmLabel}
            <div class={BLOCKING_ALERT_ACTIONS_CLASS}>
              {#if cancelLabel}
                <button
                  type="button"
                  class={BLOCKING_ALERT_SECONDARY_BUTTON_CLASS}
                  disabled={cancelDisabled}
                  onclick={() => beginClose("cancel")}
                >
                  {cancelLabel}
                </button>
              {/if}

              {#if alternativeLabel}
                <button
                  type="button"
                  class={BLOCKING_ALERT_SECONDARY_BUTTON_CLASS}
                  disabled={alternativeDisabled}
                  onclick={() => beginClose("alternative")}
                >
                  {alternativeLabel}
                </button>
              {/if}

              <PrimaryButton
                class="w-full border-primary/70 font-mono text-[11px] tracking-[0.18em] shadow-[0_10px_24px_rgba(236,72,153,0.16)] sm:w-auto"
                isSelected={true}
                disabled={confirmDisabled}
                onclick={() => beginClose("confirm")}
              >
                {#if isBusy}
                  <CircleNotch weight="regular" class="h-4 w-4 animate-spin" />
                {/if}
                {confirmLabel}
              </PrimaryButton>
            </div>
          {/if}
        </AlertDialog.Content>
      </div>
    </div>
  </AlertDialog.Portal>
</AlertDialog.Root>
