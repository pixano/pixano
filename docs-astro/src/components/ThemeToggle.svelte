<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  let theme = $state("light");

  function initTheme() {
    if (typeof document !== "undefined") {
      theme = document.documentElement.getAttribute("data-theme") || "light";
    }
  }

  function toggleTheme() {
    theme = theme === "light" ? "dark" : "light";
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("pixano-theme", theme);
  }

  // Initialize on mount
  $effect(() => {
    initTheme();
  });
</script>

<button
  class="theme-toggle"
  onclick={toggleTheme}
  aria-label="Toggle dark mode"
  title={theme === "light" ? "Switch to dark mode" : "Switch to light mode"}
>
  {#if theme === "light"}
    <!-- Moon icon -->
    <svg
      width="18"
      height="18"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      stroke-width="2"
      stroke-linecap="round"
      stroke-linejoin="round"
      class="icon"
    >
      <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path>
    </svg>
  {:else}
    <!-- Sun icon -->
    <svg
      width="18"
      height="18"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      stroke-width="2"
      stroke-linecap="round"
      stroke-linejoin="round"
      class="icon"
    >
      <circle cx="12" cy="12" r="5"></circle>
      <line x1="12" y1="1" x2="12" y2="3"></line>
      <line x1="12" y1="21" x2="12" y2="23"></line>
      <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line>
      <line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line>
      <line x1="1" y1="12" x2="3" y2="12"></line>
      <line x1="21" y1="12" x2="23" y2="12"></line>
      <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line>
      <line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line>
    </svg>
  {/if}
</button>

<style>
  .theme-toggle {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 36px;
    height: 36px;
    border: none;
    background: transparent;
    color: rgba(255, 255, 255, 0.7);
    cursor: pointer;
    border-radius: 0.5rem;
    transition: all 200ms ease;
  }

  .theme-toggle:hover {
    background: rgba(255, 255, 255, 0.1);
    color: white;
  }

  .icon {
    transition: transform 300ms ease;
  }

  .theme-toggle:hover .icon {
    transform: rotate(15deg);
  }
</style>
