<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import { onMount } from "svelte";

  let dialogEl: HTMLDialogElement | undefined = $state();
  let isOpen = $state(false);

  onMount(() => {
    // Listen for custom event from Header
    const handleOpen = () => open();
    window.addEventListener("open-search", handleOpen);

    // Keyboard shortcut: Cmd/Ctrl + K
    const handleKeydown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        if (isOpen) {
          close();
        } else {
          open();
        }
      }
      if (e.key === "Escape" && isOpen) {
        close();
      }
    };

    document.addEventListener("keydown", handleKeydown);

    // Load Pagefind UI
    loadPagefind();

    return () => {
      window.removeEventListener("open-search", handleOpen);
      document.removeEventListener("keydown", handleKeydown);
    };
  });

  async function loadPagefind() {
    try {
      // Pagefind is loaded at runtime from the built assets
      // Use dynamic URL construction to avoid Vite resolving the import
      const pagefindPath = "/pixano/pagefind/pagefind.js";
      const pagefind = await import(/* @vite-ignore */ pagefindPath);
      await pagefind.init();
      // Store reference for later use
      (window as any).__pagefind = pagefind;
    } catch (e) {
      // Pagefind may not be available in dev mode
      console.debug("Pagefind not available (expected in dev mode)");
    }
  }

  let searchQuery = $state("");
  let results: any[] = $state([]);
  let searching = $state(false);

  async function handleSearch() {
    const pf = (window as any).__pagefind;
    if (!pf || !searchQuery.trim()) {
      results = [];
      return;
    }

    searching = true;
    try {
      const search = await pf.search(searchQuery);
      const loaded = await Promise.all(
        search.results.slice(0, 8).map((r: any) => r.data())
      );
      results = loaded;
    } catch (e) {
      results = [];
    }
    searching = false;
  }

  function open() {
    isOpen = true;
    dialogEl?.showModal();
    // Focus the search input after a tick
    setTimeout(() => {
      const input = dialogEl?.querySelector("input");
      input?.focus();
    }, 50);
  }

  function close() {
    isOpen = false;
    dialogEl?.close();
    searchQuery = "";
    results = [];
  }

  function handleBackdropClick(e: MouseEvent) {
    if (e.target === dialogEl) {
      close();
    }
  }

  // Debounced search
  let searchTimeout: ReturnType<typeof setTimeout>;
  function onInput() {
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(handleSearch, 200);
  }
</script>

<!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
<dialog
  bind:this={dialogEl}
  class="search-dialog"
  onclick={handleBackdropClick}
  onkeydown={(e) => e.key === "Escape" && close()}
>
  <div class="search-container">
    <div class="search-input-wrapper">
      <svg class="search-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="11" cy="11" r="8"></circle>
        <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
      </svg>
      <input
        type="text"
        class="search-input"
        placeholder="Search documentation..."
        bind:value={searchQuery}
        oninput={onInput}
      />
      <kbd class="search-esc">Esc</kbd>
    </div>

    {#if searchQuery.trim()}
      <div class="search-results">
        {#if searching}
          <div class="search-status">Searching...</div>
        {:else if results.length === 0}
          <div class="search-status">No results found for "{searchQuery}"</div>
        {:else}
          {#each results as result}
            <a href={result.url} class="search-result" onclick={close}>
              <div class="result-title">{result.meta?.title || "Untitled"}</div>
              <div class="result-excerpt">{@html result.excerpt}</div>
            </a>
          {/each}
        {/if}
      </div>
    {:else}
      <div class="search-footer">
        <span>Type to search the documentation</span>
      </div>
    {/if}
  </div>
</dialog>

<style>
  .search-dialog {
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    border: none;
    background: transparent;
    padding: 10vh 1rem 1rem;
    max-width: 100%;
    max-height: 100%;
  }

  .search-dialog::backdrop {
    background: rgba(0, 0, 0, 0.5);
    backdrop-filter: blur(4px);
  }

  .search-container {
    width: 100%;
    max-width: 640px;
    margin: 0 auto;
    background: var(--px-bg-elevated, #fff);
    border: 1px solid var(--px-border, #e5e7eb);
    border-radius: var(--px-radius-lg, 1rem);
    box-shadow: var(--px-shadow-lg, 0 25px 50px -12px rgba(0, 0, 0, 0.25));
    overflow: hidden;
  }

  .search-input-wrapper {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    padding: 1rem 1.25rem;
    border-bottom: 1px solid var(--px-border, #e5e7eb);
  }

  .search-icon {
    color: var(--px-text-muted, #9ca3af);
    flex-shrink: 0;
  }

  .search-input {
    flex: 1;
    border: none;
    outline: none;
    font-size: 1rem;
    font-family: var(--px-font-body, system-ui);
    color: var(--px-text, #111);
    background: transparent;
    line-height: 1.5;
  }

  .search-input::placeholder {
    color: var(--px-text-muted, #9ca3af);
  }

  .search-esc {
    font-family: var(--px-font-body, system-ui);
    font-size: 0.7rem;
    padding: 0.15rem 0.4rem;
    border-radius: 0.25rem;
    background: var(--px-bg-alt, #f9fafb);
    border: 1px solid var(--px-border, #e5e7eb);
    color: var(--px-text-muted, #9ca3af);
    flex-shrink: 0;
  }

  .search-results {
    max-height: 400px;
    overflow-y: auto;
    padding: 0.5rem;
  }

  .search-result {
    display: block;
    padding: 0.75rem 1rem;
    border-radius: 0.5rem;
    text-decoration: none;
    color: inherit;
    transition: background-color 150ms ease;
  }

  .search-result:hover {
    background: var(--px-bg-alt, #f9fafb);
    text-decoration: none;
    color: inherit;
  }

  .result-title {
    font-weight: 600;
    font-size: 0.9rem;
    color: var(--px-text, #111);
    margin-bottom: 0.25rem;
  }

  .result-excerpt {
    font-size: 0.8rem;
    color: var(--px-text-secondary, #6b7280);
    line-height: 1.5;
    overflow: hidden;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
  }

  .result-excerpt :global(mark) {
    background: rgba(119, 30, 95, 0.15);
    color: var(--px-primary, #771e5f);
    border-radius: 2px;
    padding: 0 2px;
  }

  .search-status {
    padding: 1.5rem;
    text-align: center;
    font-size: 0.875rem;
    color: var(--px-text-muted, #9ca3af);
  }

  .search-footer {
    padding: 0.75rem 1.25rem;
    font-size: 0.8rem;
    color: var(--px-text-muted, #9ca3af);
    text-align: center;
  }
</style>
