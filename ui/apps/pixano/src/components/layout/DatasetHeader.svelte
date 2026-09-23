<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { fade } from "svelte/transition";

  import WorkspaceRecordHeader from "./WorkspaceRecordHeader.svelte";
  import { navigating, page } from "$app/state";
  import * as api from "$lib/api";
  import type { NeighborsResponse } from "$lib/api/restTypes";
  import { currentDatasetStore, currentItemSaveCoordinator } from "$lib/stores/appStores.svelte";
  import { navigateToRoute } from "$lib/utils/navigation";
  import {
    getExplorerRoute,
    getPageFromPosition,
    getRouteSearchParams,
    getWorkspaceRoute,
    pickExplorerQuery,
    WORKSPACE_ROUTE_ID,
  } from "$lib/utils/routes";

  let currentItemId = $derived(page.params.itemId);
  const isWorkspaceRoute = $derived(page.route.id === WORKSPACE_ROUTE_ID);
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
  const neighborsContext = $derived(
    JSON.stringify([currentDatasetStore.value?.id, currentItemId, explorerQuery()]),
  );
  let neighborResult = $state<{ context: string; data: NeighborsResponse } | null>(null);
  const neighbors = $derived(
    neighborResult?.context === neighborsContext ? neighborResult.data : null,
  );
  $effect(() => {
    const context = neighborsContext;
    const datasetId = currentDatasetStore.value?.id;
    const itemId = currentItemId;
    neighborResult = null;
    if (!isWorkspaceRoute || !datasetId || !itemId) {
      return;
    }
    const query = explorerQuery();
    let cancelled = false;
    void api
      .getNeighbors(datasetId, itemId, query)
      .then((result) => {
        if (!cancelled) neighborResult = { context, data: result };
      })
      .catch(() => {
        if (!cancelled) neighborResult = null;
      });
    return () => {
      cancelled = true;
    };
  });

  const getRecordPosition = () => ({
    position: neighbors?.position ?? null,
    total: neighbors?.total ?? null,
  });

  // Handle bi-directional navigation using arrows
  const goToNeighborItem = async (direction: "previous" | "next") => {
    if (navigating.to !== null) return;
    if (!currentDatasetStore.value || !neighbors) return;

    const neighborId = direction === "previous" ? neighbors.prev : neighbors.next;
    if (!neighborId) return; // at the start/end of the filtered result set

    const query = pickExplorerQuery(getRouteSearchParams(page.url)).toString();
    const route = getWorkspaceRoute(currentDatasetStore.value.id, neighborId, query);

    await navigateToRoute(route);
  };

  const handleSave = () => {
    void currentItemSaveCoordinator.requestSave();
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
      await navigateToRoute(getExplorerRoute(currentDatasetStore.value.id, params.toString()));
    } else await navigateToRoute("/");
  };
</script>

<div class="h-full w-full flex items-center">
  {#if isWorkspaceRoute}
    <WorkspaceRecordHeader
      {currentItemId}
      {handleSave}
      {goToNeighborItem}
      {handleReturnToPreviousPage}
      {getRecordPosition}
    />
  {:else}
    <!-- Breadcrumb: Library / dataset name -->
    <nav in:fade={{ duration: 200 }} class="flex-1 flex items-center gap-2 h-full min-w-0">
      <button
        type="button"
        onclick={() => navigateToRoute("/")}
        class="text-sm font-medium text-muted-foreground hover:text-primary transition-colors rounded-md px-1 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        Library
      </button>
      <span class="shrink-0 text-sm text-muted-foreground/40">/</span>
      {#if currentDatasetStore.value}
        <span class="max-w-[360px] truncate text-sm font-bold text-foreground">
          {currentDatasetStore.value.name}
        </span>
      {/if}
    </nav>
  {/if}
</div>
