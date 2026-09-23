<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { afterNavigate, beforeNavigate, goto } from "$app/navigation";
  import { page } from "$app/state";
  import { currentItemSaveCoordinator } from "$lib/stores/appStores.svelte";
  import {
    createNavigationGuard,
    isNavigationCancellation,
    replayNavigation,
    saveBeforeNavigation,
    type GuardedNavigation,
  } from "$lib/stores/navigationGuard";
  import { canSave } from "$lib/stores/workspaceStores.svelte";
  import { UnsavedChangesDialog } from "$lib/ui";
  import { WORKSPACE_ROUTE_ID } from "$lib/utils/routes";

  let pending = $state<GuardedNavigation | null>(null);
  let resuming = $state(false);
  let navigationError = $state<string | null>(null);
  const guard = createNavigationGuard((next) => (pending = next));
  const saveState = $derived(currentItemSaveCoordinator.value);
  let restoredHistory: Promise<boolean> = Promise.resolve(true);
  let historyReplay: {
    intent: GuardedNavigation;
    resolve: () => void;
    reject: (error: unknown) => void;
  } | null = null;

  const recordKey = (
    target: {
      route: { id: string | null };
      params: Record<string, string | undefined> | null;
    } | null,
  ) =>
    target?.route.id === WORKSPACE_ROUTE_ID
      ? `${target.params?.datasetId}/${target.params?.itemId}`
      : null;

  // Cancelled popstate navigation is reversed asynchronously by SvelteKit.
  function waitForHistoryRestore(url: string): Promise<boolean> {
    if (window.location.href === url) return Promise.resolve(true);
    return new Promise((resolve) => {
      const finish = (restored: boolean) => {
        window.removeEventListener("popstate", check);
        clearTimeout(timeout);
        resolve(restored);
      };
      const check = () => {
        if (window.location.href === url) finish(true);
      };
      const timeout = setTimeout(() => finish(false), 5000);
      window.addEventListener("popstate", check);
    });
  }

  beforeNavigate((navigation) => {
    const intent: GuardedNavigation = {
      from: navigation.from?.url.href ?? page.url.href,
      to: navigation.to?.url.href ?? "",
      fromRecord: recordKey(navigation.from),
      toRecord: recordKey(navigation.to),
      type: navigation.type,
      delta: navigation.delta,
      willUnload: navigation.willUnload,
    };
    const hadPending = guard.pending !== null;
    const decision = guard.intercept(intent, {
      isDirty: canSave.value,
      isSaving: saveState.status === "saving",
    });
    const replay = historyReplay;
    const isHistoryReplay =
      replay &&
      intent.type === "popstate" &&
      (intent.to === replay.intent.to ||
        (intent.toRecord !== null && intent.toRecord === replay.intent.toRecord));
    if (decision === "allow") {
      if (isHistoryReplay) void navigation.complete.then(replay.resolve, replay.reject);
      return;
    }
    // On unload SvelteKit uses the native browser confirmation.
    navigation.cancel();
    if (isHistoryReplay) replay.reject(new Error("navigation cancelled"));
    if (decision === "unload") return;
    if (!hadPending) {
      navigationError = null;
      restoredHistory =
        intent.type === "popstate" ? waitForHistoryRestore(intent.from) : Promise.resolve(true);
      if (saveState.status === "saving") void handleSaveAndContinue();
    }
  });

  afterNavigate((navigation) => {
    if (pending?.to === navigation.to?.url.href) guard.clear();
  });

  $effect(() => {
    if (page.route.id !== WORKSPACE_ROUTE_ID) currentItemSaveCoordinator.resetForItemChange();
  });

  async function replay(intent: GuardedNavigation) {
    await replayNavigation(intent, {
      restoreHistory: async () => {
        if (!(await restoredHistory)) throw new Error("Browser history could not be restored.");
      },
      goto: async (url) => {
        await goto(url);
      },
      historyGo: (delta) =>
        new Promise<void>((resolve, reject) => {
          const finish = (error?: unknown) => {
            clearTimeout(timeout);
            historyReplay = null;
            if (error)
              reject(error instanceof Error ? error : new Error("Browser navigation failed."));
            else resolve();
          };
          const timeout = setTimeout(() => {
            finish(new Error("Browser navigation did not finish. Try again."));
          }, 10000);
          historyReplay = {
            intent,
            resolve: () => finish(),
            reject: finish,
          };
          window.history.go(delta);
        }),
    });
  }

  async function handleSaveAndContinue() {
    if (resuming) return;
    resuming = true;
    navigationError = null;
    try {
      // Sync directly: a just-staged edit may precede the route's reactive effect.
      currentItemSaveCoordinator.syncDirty(canSave.value);
      await saveBeforeNavigation(
        guard,
        currentItemSaveCoordinator.requestSave,
        () => canSave.value,
        replay,
      );
    } catch (error) {
      if (!isNavigationCancellation(error)) {
        navigationError = error instanceof Error ? error.message : "Navigation failed. Try again.";
      }
    } finally {
      resuming = false;
    }
  }

  async function handleDiscardAndContinue() {
    if (resuming || saveState.status === "saving") return;
    const intent = guard.authorizeDiscard();
    if (!intent) return;
    resuming = true;
    navigationError = null;
    try {
      await replay(intent);
      if (guard.pending === intent) guard.clear();
    } catch (error) {
      if (!isNavigationCancellation(error)) {
        navigationError = error instanceof Error ? error.message : "Navigation failed. Try again.";
      }
    } finally {
      guard.rearm();
      resuming = false;
    }
  }
</script>

{#if pending}
  <UnsavedChangesDialog
    isSaving={saveState.status === "saving" || resuming}
    errorMessage={navigationError ?? saveState.errorMessage}
    onSave={handleSaveAndContinue}
    onDiscard={handleDiscardAndContinue}
    onCancel={() => guard.clear()}
  />
{/if}
