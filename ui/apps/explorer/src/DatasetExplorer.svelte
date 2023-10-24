<script lang="ts">
  /**
   * @copyright CEA
   * @author CEA
   * @license CECILL
   *
   * This software is a collaborative computer program whose purpose is to
   * generate and explore labeled data for computer vision applications.
   * This software is governed by the CeCILL-C license under French law and
   * abiding by the rules of distribution of free software. You can use,
   * modify and/ or redistribute the software under the terms of the CeCILL-C
   * license as circulated by CEA, CNRS and INRIA at the following URL
   *
   * http://www.cecill.info
   */

  // Imports
  import { createEventDispatcher, onMount } from "svelte";

  import { api, Dashboard } from "@pixano/core";
  
  import { Table } from "@pixano/table";

  import type { Dataset } from "@pixano/core";
  import {
    svg_filter,
    svg_first_page,
    svg_grid,
    svg_last_page,
    svg_list,
    svg_next_page,
    svg_prev_page,
    svg_search,
  } from "@pixano/core/src/icons";

  // Exports
  export let selectedDataset: Dataset;
  export let selectedTab: string;
  export let currentPage: number;

  let datasetStats = null;
 
  let query = null;

  // Page navigation
  const itemsPerPage = 100;

  const dispatch = createEventDispatcher();

  function handleSelectItem(itemId: string) {
    dispatch("selectItem", itemId);

    selectedTab = "";
  }

  async function loadPage() {
    selectedDataset.page = null;
    const start = Date.now();
    selectedDataset.page = await api.getDatasetItems(
      selectedDataset.id,
      currentPage,
      itemsPerPage
    );
    console.log(
      "DatasetExplorer.loadPage - api.getDatasetItems in",
      Date.now() - start,
      "ms"
    );

    // If no dataset page, return error message
    if (selectedDataset.page == null) {
      dispatch("datasetError");
    }
  }

  async function handleGoToFirstPage() {
    if (currentPage > 1) {
      currentPage = 1;
      loadPage();
    }
  }

  async function handleGoToPreviousPage() {
    if (currentPage > 1) {
      currentPage -= 1;
      loadPage();
    }
  }

  async function handleGoToNextPage() {
    if (selectedDataset.page.total > currentPage * itemsPerPage) {
      currentPage += 1;
      loadPage();
    }
  }

  async function handleGoToLastPage() {
    if (selectedDataset.page.total > currentPage * itemsPerPage) {
      currentPage = Math.ceil(selectedDataset.page.total / itemsPerPage);
      loadPage();
    }
  }

  async function handleSearchEnter(query_str: string) {
    query = query_str;
    if (query_str == "") {
      loadPage()
    } else {
      const start = Date.now();
      let actual_page = selectedDataset.page
      selectedDataset.page = null; //required to refresh column names -- TODO: better refresh?
      let res = await api.getSearchResult(
        selectedDataset.id,
        query,
        currentPage,
        itemsPerPage
      );
      console.log(
        "DatasetExplorer.handleSearchEnter - api.getSearchResult in",
        Date.now() - start,
        "ms"
      );
      // If no dataset page, return error message
      if (res == null) {
        selectedDataset.page = actual_page;
        dispatch("searchError");
      } else {
        selectedDataset.page = res;
      }
    }
  }



  onMount(async () => {
    loadPage();
    datasetStats = await api.getDatasetStats(selectedDataset.id);
  });
</script>

<div
  class="w-full h-full pt-20 px-20 flex flex-col bg-slate-100 text-slate-800"
>
  {#if selectedDataset.page}
    <!-- Items list -->
    <div class="w-full h-[87.5vh] flex flex-col">
      <div class="py-4 flex space-x-2 items-center">
        {#if selectedTab === "database"}
          <button>
            <svg
              xmlns="http://www.w3.org/2000/svg"
              height="48"
              viewBox="0 -960 960 960"
              width="48"
              class="h-8 w-8 p-1 rounded-full hover:bg-slate-300"
            >
              <path d={svg_list} fill="currentcolor" />
            </svg>
          </button>
          <button>
            <svg
              xmlns="http://www.w3.org/2000/svg"
              height="48"
              viewBox="0 -960 960 960"
              width="48"
              class="h-8 w-8 p-1 rounded-full hover:bg-slate-300"
            >
              <path d={svg_grid} fill="currentcolor" />
            </svg>
          </button>
        {/if}
        <button>
          <svg
            xmlns="http://www.w3.org/2000/svg"
            height="48"
            viewBox="0 -960 960 960"
            width="48"
            class="h-8 w-8 p-1 rounded-full hover:bg-slate-300"
          >
            <path d={svg_filter} fill="currentcolor" />
          </svg>
        </button>
        <div class="flex-grow" />
        <div class="relative flex items-center">
          <input
            type="text"
            placeholder="Search"
            value={query}
            class="h-8 pl-8 pr-4 border rounded-sm border-slate-300 shadow-slate-300 accent-main"
            on:change={(event) => handleSearchEnter(event.srcElement.value)}
          />
          <svg
            xmlns="http://www.w3.org/2000/svg"
            height="48"
            viewBox="0 -960 960 960"
            width="48"
            class="absolute left-2 h-4 w-4 pointer-events-none"
          >
            <path d={svg_search} />
          </svg>
        </div>
      </div>
      {#if selectedTab === "database"}
        <Table
          data={selectedDataset.page.items}
          on:selectItem={(event) => handleSelectItem(event.detail)}
        />
      {:else if selectedTab === "dashboard"}
        <Dashboard {selectedDataset} {datasetStats} />
      {/if}
    </div>

    <!-- Page navigation -->
    {#if selectedTab === "database"}
      <div class="w-full my-3 flex justify-center items-center text-slate-800">
        {#if selectedDataset.page.total > itemsPerPage}
          <button on:click={handleGoToFirstPage}>
            <svg
              xmlns="http://www.w3.org/2000/svg"
              height="48"
              viewBox="0 -960 960 960"
              width="48"
              class="h-8 w-8 p-1 rounded-full hover:bg-slate-300"
            >
              <path d={svg_first_page} fill="currentcolor" />
            </svg>
          </button>

          <button on:click={handleGoToPreviousPage}>
            <svg
              xmlns="http://www.w3.org/2000/svg"
              height="48"
              viewBox="0 -960 960 960"
              width="48"
              class="h-8 w-8 p-1 rounded-full hover:bg-slate-300"
            >
              <path d={svg_prev_page} fill="currentcolor" />
            </svg>
          </button>
        {/if}

        <span class="mx-4">
          {1 + itemsPerPage * (currentPage - 1)} - {Math.min(
            itemsPerPage * currentPage,
            selectedDataset.page.total
          )} of
          {selectedDataset.page.total}
        </span>

        {#if selectedDataset.page.total > itemsPerPage}
          <button on:click={handleGoToNextPage}>
            <svg
              xmlns="http://www.w3.org/2000/svg"
              height="48"
              viewBox="0 -960 960 960"
              width="48"
              class="h-8 w-8 p-1 rounded-full hover:bg-slate-300"
            >
              <path d={svg_next_page} fill="currentcolor" />
            </svg>
          </button>

          <button on:click={handleGoToLastPage}>
            <svg
              xmlns="http://www.w3.org/2000/svg"
              height="48"
              viewBox="0 -960 960 960"
              width="48"
              class="h-8 w-8 p-1 rounded-full hover:bg-slate-300"
            >
              <path d={svg_last_page} fill="currentcolor" />
            </svg>
          </button>
        {/if}
      </div>
    {/if}
  {/if}
</div>
