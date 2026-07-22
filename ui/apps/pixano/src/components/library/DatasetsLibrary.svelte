<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  // Imports
  import { ArrowRight, Database, UploadSimple } from "phosphor-svelte";
  import { untrack } from "svelte";

  import DatasetPreviewCard from "../../components/dataset/DatasetPreviewCard.svelte";
  import { panTool } from "../workspace";
  import ImportWizard from "./import-wizard/ImportWizard.svelte";
  import { goto } from "$app/navigation";
  import { datasetFilter, datasetSortMode, datasetsStore } from "$lib/stores/appStores.svelte";
  import { modelsUiStore, resetColorScale, selectedTool } from "$lib/stores/workspaceStores.svelte";
  import type { DatasetInfo } from "$lib/ui";
  import { icons } from "$lib/ui";
  import { sortDatasets } from "$lib/utils/datasetSort";
  import { getExplorerRoute } from "$lib/utils/routes";

  /**
   * DatasetsLibrary Component
   *
   * This component displays a list of datasets. Each dataset is represented by a
   * DatasetPreviewCard component. When a dataset is selected, the user is navigated
   * to the dataset's detail page.
   *
   * Data comes from datasetsStore
   *   - datasets: Array<DatasetInfo> - An array of dataset information objects.
   *
   * Events:
   *   - selectDataset: Triggered when a dataset is selected.
   */

  let showImport = $state(false);

  const BOOKMARK_SECTIONS: {
    key: string;
    label: string;
    color: string;
    bgClass: string;
    textClass: string;
  }[] = [
    {
      key: "TODO",
      label: "TODO",
      color: "#3B82F6",
      bgClass: "bg-blue-500/10",
      textClass: "text-blue-500",
    },
    {
      key: "NEW",
      label: "NEW",
      color: "#22C55E",
      bgClass: "bg-green-500/10",
      textClass: "text-green-500",
    },
    {
      key: "FAVORITE",
      label: "FAVORITE",
      color: "#EAB308",
      bgClass: "bg-yellow-500/10",
      textClass: "text-yellow-500",
    },
  ];

  const allDatasets = $derived(datasetsStore.value);

  const filteredDatasets = $derived(allDatasets.filter((d) => !d.isFiltered));

  const sortedDatasets = $derived(sortDatasets(filteredDatasets, datasetSortMode.value));

  const datasetsByBookmark = $derived(
    Object.fromEntries(
      BOOKMARK_SECTIONS.map((s) => [
        s.key,
        sortedDatasets.filter((d) => d.bookmarks.includes(s.key)),
      ]),
    ),
  );

  const hasAnyBookmarks = $derived(sortedDatasets.some((d) => d.bookmarks.length > 0));

  const remainingDatasets = $derived(
    hasAnyBookmarks ? sortedDatasets.filter((d) => d.bookmarks.length === 0) : sortedDatasets,
  );

  const handleSelectDataset = async (dataset: DatasetInfo) => {
    await goto(getExplorerRoute(dataset.id));
  };

  const handleSearch = (e: Event) => {
    const target = e.currentTarget as HTMLInputElement;
    datasetFilter.value = target.value;
    datasetsStore.update((value = []) =>
      value.map((dataset) => ({
        ...dataset,
        isFiltered: !dataset.name.toLocaleLowerCase().includes(target.value.toLocaleLowerCase()),
      })),
    );
  };

  $effect(() => {
    untrack(() => {
      resetColorScale();
      modelsUiStore.value = {
        currentModalOpen: "none",
        selectedModelName: "",
        selectedTableName: "",
        yetToLoadEmbedding: true,
      };
      selectedTool.value = panTool;
    });
  });
</script>

{#if showImport}
  <ImportWizard
    onClose={() => {
      showImport = false;
    }}
  />
{/if}

{#if allDatasets && allDatasets.length > 0}
  <div class="flex flex-col gap-8">
    <!-- Toolbar: search + sort + stats -->
    <div class="flex items-center justify-between gap-6 flex-wrap pb-2 border-b border-border/50">
      <div class="relative flex items-center group">
        <input
          id="search-input"
          type="text"
          placeholder="Search datasets..."
          class="h-10 w-72 pl-10 pr-4 rounded-xl bg-muted/50 border border-border
          text-foreground placeholder-muted-foreground/60 text-sm focus:outline-none focus:ring-2 focus:ring-primary/20 focus:bg-background transition-all duration-200 shadow-sm"
          oninput={handleSearch}
          value={datasetFilter.value}
        />
        <svg
          xmlns="http://www.w3.org/2000/svg"
          height="48"
          viewBox="0 -960 960 960"
          width="48"
          class="absolute left-3.5 h-4 w-4 pointer-events-none text-muted-foreground/60 group-focus-within:text-primary transition-colors"
        >
          <path d={icons.svg_search} fill="currentColor" />
        </svg>
      </div>
      <div class="flex items-center gap-4">
        <!-- Sort controls -->
        <div class="flex items-center rounded-xl border border-border overflow-hidden shadow-sm">
          <button
            class="px-3 py-1.5 text-xs font-bold uppercase tracking-wider transition-colors {datasetSortMode.value ===
            'name'
              ? 'bg-primary text-primary-foreground'
              : 'bg-background text-muted-foreground hover:text-foreground'}"
            onclick={() => (datasetSortMode.value = "name")}
          >
            Name
          </button>
          <button
            class="px-3 py-1.5 text-xs font-bold uppercase tracking-wider transition-colors {datasetSortMode.value ===
            'creation_date'
              ? 'bg-primary text-primary-foreground'
              : 'bg-background text-muted-foreground hover:text-foreground'}"
            onclick={() => (datasetSortMode.value = "creation_date")}
          >
            Date
          </button>
        </div>
        <button
          onclick={() => {
            showImport = true;
          }}
          class="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-xl bg-primary text-primary-foreground
            text-xs font-bold uppercase tracking-wider shadow-sm hover:bg-primary/90 active:scale-95
            transition-all duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <UploadSimple weight="bold" size={14} />
          Import
        </button>
        <div
          class="px-3.5 py-1.5 rounded-xl bg-background border border-border flex items-center gap-2.5 shadow-sm"
        >
          <span class="text-xs font-bold text-muted-foreground uppercase tracking-wider">
            Datasets
          </span>
          <span class="text-sm font-black text-primary tabular-nums">
            {allDatasets.length}
          </span>
        </div>
        <div
          class="px-3.5 py-1.5 rounded-xl bg-background border border-border flex items-center gap-2.5 shadow-sm"
        >
          <span class="text-xs font-bold text-muted-foreground uppercase tracking-wider">
            Total Items
          </span>
          <span class="text-sm font-black text-primary tabular-nums">
            {allDatasets.reduce((sum, dataset) => sum + dataset.num_items, 0)}
          </span>
        </div>
      </div>
    </div>

    <!-- Bookmark sections -->
    {#each BOOKMARK_SECTIONS as section (section.key)}
      {#if datasetsByBookmark[section.key].length > 0}
        <div class="flex flex-col gap-4">
          <div class="flex items-center gap-2.5">
            <span
              class="px-2.5 py-0.5 rounded-full text-[11px] font-black uppercase tracking-widest {section.bgClass} {section.textClass}"
            >
              {section.label}
            </span>
            <span class="text-xs text-muted-foreground font-medium">
              {datasetsByBookmark[section.key].length} dataset{datasetsByBookmark[section.key]
                .length > 1
                ? "s"
                : ""}
            </span>
          </div>
          <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
            {#each datasetsByBookmark[section.key] as dataset (dataset.id)}
              <div class="animate-in fade-in slide-in-from-bottom-2 duration-500">
                <DatasetPreviewCard
                  {dataset}
                  onSelectDataset={() => handleSelectDataset(dataset)}
                />
              </div>
            {/each}
          </div>
        </div>
      {/if}
    {/each}

    <!-- All / Other datasets -->
    <div class="flex flex-col gap-4">
      <div class="flex items-center gap-2.5">
        <span
          class="px-2.5 py-0.5 rounded-full text-[11px] font-black uppercase tracking-widest bg-muted text-muted-foreground"
        >
          {hasAnyBookmarks ? "Other datasets" : "All datasets"}
        </span>
        <span class="text-xs text-muted-foreground font-medium">
          {remainingDatasets.length} dataset{remainingDatasets.length > 1 ? "s" : ""}
        </span>
      </div>
      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
        {#each remainingDatasets as dataset (dataset.id)}
          <div class="animate-in fade-in slide-in-from-bottom-2 duration-500">
            <DatasetPreviewCard {dataset} onSelectDataset={() => handleSelectDataset(dataset)} />
          </div>
        {/each}
      </div>
    </div>
  </div>
{:else if allDatasets}
  <!-- Empty library -->
  <div class="flex flex-col items-center justify-center h-full text-center">
    <div class="w-20 h-20 rounded-2xl bg-primary/5 flex items-center justify-center mb-8">
      <Database weight="thin" size={44} class="text-primary/40" />
    </div>

    <h2 class="text-2xl font-bold tracking-tight text-foreground">Your library is empty</h2>

    <p class="mt-3 text-sm text-muted-foreground max-w-md leading-relaxed">
      Import a folder of images or videos to start your annotation workflow.
    </p>

    <button
      onclick={() => {
        showImport = true;
      }}
      class="mt-8 inline-flex items-center gap-2 h-11 px-6 rounded-xl bg-primary text-primary-foreground
        text-sm font-bold uppercase tracking-widest shadow-sm hover:bg-primary/90 active:scale-95
        transition-all duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
    >
      <UploadSimple weight="bold" size={16} />
      Import dataset
    </button>

    <a
      href="https://pixano.github.io/pixano/latest/getting_started/"
      target="_blank"
      rel="noopener noreferrer"
      class="mt-5 inline-flex items-center gap-1.5 text-sm font-medium text-muted-foreground hover:text-primary hover:underline transition-colors"
    >
      Read the getting started guide
      <ArrowRight weight="bold" size={14} />
    </a>
  </div>
{:else}
  <!-- Loading skeleton -->
  <div class="flex flex-col gap-8 px-6 py-8">
    <div class="max-w-[1200px] mx-auto w-full">
      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
        {#each [0, 1, 2, 3, 4, 5, 6, 7] as i (i)}
          <div
            class="flex flex-col rounded-2xl border border-border bg-card animate-pulse overflow-hidden"
          >
            <div class="aspect-video bg-muted/50 w-full"></div>
            <div class="p-5 space-y-4">
              <div class="space-y-2">
                <div class="h-4 w-2/3 bg-muted rounded-full"></div>
              </div>
              <div class="space-y-2">
                <div class="h-2 w-full bg-muted/40 rounded-full"></div>
                <div class="h-2 w-4/5 bg-muted/40 rounded-full"></div>
              </div>
              <div class="pt-4 border-t border-border/40 flex gap-4">
                <div class="h-3 w-12 bg-muted/50 rounded-full"></div>
                <div class="h-3 w-12 bg-muted/50 rounded-full"></div>
              </div>
            </div>
          </div>
        {/each}
      </div>
    </div>
  </div>
{/if}
