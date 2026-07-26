<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { CaretRight } from "phosphor-svelte";
  import { fade } from "svelte/transition";

  import WorkspaceRecordHeader from "./WorkspaceRecordHeader.svelte";
  import { goto } from "$app/navigation";
  import { page } from "$app/state";
  import * as api from "$lib/api";
  import type { NeighborsResponse } from "$lib/api/restTypes";
  import { currentDatasetStore, currentItemSaveCoordinator } from "$lib/stores/appStores.svelte";
  import { UnsavedChangesDialog } from "$lib/ui";
  import {
    getExplorerRoute,
    getPageFromPosition,
    getRouteSearchParams,
    getWorkspaceRoute,
    pickExplorerQuery,
    WORKSPACE_ROUTE_ID,
  } from "$lib/utils/routes";

  let pendingNavigationRoute = $state<string | null>(null);
  let isDestroyed = false;

  let currentItemId = $derived(page.params.itemId);
  const isWorkspaceRoute = $derived(page.route.id === WORKSPACE_ROUTE_ID);
  const saveState = $derived(currentItemSaveCoordinator.value);

  $effect(() => {
    return () => {
      isDestroyed = true;
    };
  });

  $effect(() => {
    if (page.route.id === WORKSPACE_ROUTE_ID) return;
    currentItemSaveCoordinator.resetForItemChange();
  });

  // The active filter/sort/search, read from the workspace route's hash query.
  const explorerQuery = () => {
    const params = getRouteSearchParams(page.url);
    return {
      filters: params.getAll("filter").filter((value) => value !== ""),
      q: params.get("q") ?? undefined,
      sort: params.get("sort") ?? undefined,
      order: params.get("order") ?? undefined,
      where: params.get("where") ?? undefined,
    };
  };

  // Neighbors within the current result set, fetched server-side so item-to-item
  // navigation honors the explorer's filter and sort (not the full dataset).
  let neighbors = $state<NeighborsResponse | null>(null);
  $effect(() => {
    const datasetId = currentDatasetStore.value?.id;
    const itemId = currentItemId;
    if (!isWorkspaceRoute || !datasetId || !itemId) {
      neighbors = null;
      return;
    }
    const query = explorerQuery();
    let cancelled = false;
    void api.getNeighbors(datasetId, itemId, query).then((result) => {
      if (!cancelled) neighbors = result;
    });
    return () => {
      cancelled = true;
    };
  });

  const getWorkspaceRecordDisplayCount = () => {
    if (!neighbors || neighbors.position == null) return "0 of 0";
    return `${neighbors.position} of ${neighbors.total}`;
  };

  // Handle bi-directional navigation using arrows
  const goToNeighborItem = async (direction: "previous" | "next") => {
    if (!currentDatasetStore.value || !neighbors) return;

    const neighborId = direction === "previous" ? neighbors.prev : neighbors.next;
    if (!neighborId) return; // at the start/end of the filtered result set

    const query = pickExplorerQuery(getRouteSearchParams(page.url)).toString();
    const route = getWorkspaceRoute(currentDatasetStore.value.id, neighborId, query);

    // Ask for confirmation if modifications have been made to the item
    if (saveState.isDirty) {
      pendingNavigationRoute = route;
      return;
    }

    // Go to next/previous item
    await goto(route);
  };

  const handleSave = () => {
    void currentItemSaveCoordinator.requestSave();
  };

  const handleSaveAndContinue = async () => {
    const route = pendingNavigationRoute;
    if (!route) return;

    const result = await currentItemSaveCoordinator.requestSave();
    if (!result.ok) return;

    pendingNavigationRoute = null;
    await goto(route);
  };

  const handleDiscardAndContinue = async () => {
    const route = pendingNavigationRoute;
    if (!route) return;

    pendingNavigationRoute = null;
    currentItemSaveCoordinator.beginDiscardBypass();

    try {
      await goto(route);
    } finally {
      if (!isDestroyed) {
        currentItemSaveCoordinator.endDiscardBypass();
      }
    }
  };

  // Return to the explorer, landing on the page that contains this item within
  // the active filter/sort (derived from its position in the result set).
  const handleReturnToPreviousPage = async () => {
    if (!currentDatasetStore.value) return;
    if (currentItemId) {
      const params = pickExplorerQuery(getRouteSearchParams(page.url));
      // Respect a custom page size so the computed page matches the explorer's pagination.
      const size = parseInt(params.get("size") ?? "") || undefined;
      params.set("page", String(getPageFromPosition(neighbors?.position ?? 1, size)));
      await navigateTo(getExplorerRoute(currentDatasetStore.value.id, params.toString()));
    } else await navigateTo("/");
  };

  const navigateTo = async (route: string) => {
    if (saveState.isDirty) {
      pendingNavigationRoute = route;
      return;
    }
    await goto(route);
  };

  // Prevent losing unsaved changes on browser-level unloads.
  // Internal app navigation is handled by the dialog flow above.
  // The parameter is unused but required by the Svelte action signature.
  // eslint-disable-next-line
  function preventUnsavedUnload(_: HTMLElement) {
    function checkNavigation(e: BeforeUnloadEvent) {
      if (
        currentItemSaveCoordinator.value.isDirty &&
        currentItemSaveCoordinator.value.guardMode === "armed"
      ) {
        e.preventDefault();
      }
    }
    window.addEventListener("beforeunload", checkNavigation);
    return {
      destroy() {
        window.removeEventListener("beforeunload", checkNavigation);
      },
    };
  }
</script>

<div class="h-full w-full flex items-center" use:preventUnsavedUnload>
  {#if isWorkspaceRoute}
    <WorkspaceRecordHeader
      {currentItemId}
      {handleSave}
      {goToNeighborItem}
      {handleReturnToPreviousPage}
      {getWorkspaceRecordDisplayCount}
    />
  {:else}
    <!-- Breadcrumb: Library › dataset name -->
    <nav in:fade={{ duration: 200 }} class="flex-1 flex items-center gap-2 h-full min-w-0">
      <button
        type="button"
        onclick={() => navigateTo("/")}
        class="text-sm font-medium text-muted-foreground hover:text-primary transition-colors rounded-md px-1 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        Library
      </button>
      <CaretRight size={14} class="shrink-0 text-muted-foreground/50" />
      {#if currentDatasetStore.value}
        <div
          class="flex items-center px-4 py-1.5 bg-primary/[0.03] border border-primary/10 rounded-xl max-w-[360px]"
        >
          <span class="text-sm font-bold text-foreground truncate">
            {currentDatasetStore.value.name}
          </span>
        </div>
      {/if}
    </nav>
  {/if}
</div>
{#if pendingNavigationRoute !== null}
  <UnsavedChangesDialog
    isSaving={saveState.status === "saving"}
    errorMessage={saveState.status === "failed" ? saveState.errorMessage : null}
    onSave={handleSaveAndContinue}
    onDiscard={handleDiscardAndContinue}
    onCancel={() => (pendingNavigationRoute = null)}
  />
{/if}
