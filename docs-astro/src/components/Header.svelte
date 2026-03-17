<script lang="ts">
  import ThemeToggle from "./ThemeToggle.svelte";

  interface Props {
    currentPath?: string;
    basePath?: string;
  }

  let { currentPath = "", basePath = "/pixano" }: Props = $props();

  const navItems = [
    { title: "Getting Started", href: `${basePath}/getting_started/` },
    { title: "Tutorials", href: `${basePath}/tutorials/` },
    { title: "API Reference", href: `${basePath}/api_reference/` },
  ];

  let mobileMenuOpen = $state(false);

  function isActive(href: string): boolean {
    return currentPath.startsWith(href);
  }

  function toggleMobileMenu() {
    mobileMenuOpen = !mobileMenuOpen;
  }

  function handleSearchClick() {
    window.dispatchEvent(new CustomEvent("open-search"));
  }
</script>

<header class="header">
  <div class="header-inner">
    <!-- Logo -->
    <a href="{basePath}/getting_started/" class="logo">
      <img
        src="{basePath}/assets/pixano_white.png"
        alt="Pixano"
        width="28"
        height="28"
      />
      <span class="logo-text">Pixano</span>
      <span class="logo-badge">Docs</span>
    </a>

    <!-- Desktop Navigation -->
    <nav class="nav-desktop" aria-label="Main navigation">
      {#each navItems as item}
        <a
          href={item.href}
          class="nav-link"
          class:active={isActive(item.href)}
          aria-current={isActive(item.href) ? "page" : undefined}
        >
          {item.title}
        </a>
      {/each}
    </nav>

    <!-- Actions -->
    <div class="header-actions">
      <!-- Search button -->
      <button
        class="search-trigger"
        onclick={handleSearchClick}
        aria-label="Search documentation"
      >
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="11" cy="11" r="8"></circle>
          <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
        </svg>
        <span class="search-label">Search</span>
        <kbd class="search-kbd">
          <span class="search-kbd-meta">&#8984;</span>K
        </kbd>
      </button>

      <!-- GitHub -->
      <a
        href="https://github.com/pixano/pixano"
        class="icon-btn"
        target="_blank"
        rel="noopener noreferrer"
        aria-label="GitHub repository"
      >
        <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
          <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/>
        </svg>
      </a>

      <!-- Theme toggle -->
      <ThemeToggle />

      <!-- Mobile menu button -->
      <button
        class="mobile-menu-btn"
        onclick={toggleMobileMenu}
        aria-label="Toggle navigation menu"
        aria-expanded={mobileMenuOpen}
      >
        {#if mobileMenuOpen}
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
            <line x1="18" y1="6" x2="6" y2="18"></line>
            <line x1="6" y1="6" x2="18" y2="18"></line>
          </svg>
        {:else}
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
            <line x1="3" y1="6" x2="21" y2="6"></line>
            <line x1="3" y1="12" x2="21" y2="12"></line>
            <line x1="3" y1="18" x2="21" y2="18"></line>
          </svg>
        {/if}
      </button>
    </div>
  </div>

  <!-- Mobile Navigation -->
  {#if mobileMenuOpen}
    <nav class="nav-mobile" aria-label="Mobile navigation">
      {#each navItems as item}
        <a
          href={item.href}
          class="nav-mobile-link"
          class:active={isActive(item.href)}
        >
          {item.title}
        </a>
      {/each}
    </nav>
  {/if}
</header>

<style>
  /* ── Floating Glass Pill Header ── */
  .header {
    position: sticky;
    top: 0.75rem;
    z-index: 50;
    margin: 0.75rem 1.5rem 0;
    background: var(--px-glass-bg-dense);
    backdrop-filter: var(--px-glass-blur);
    -webkit-backdrop-filter: var(--px-glass-blur);
    border: 1px solid var(--px-glass-border);
    border-radius: var(--px-radius-xl);
    box-shadow:
      var(--px-glow-primary),
      var(--px-glass-shadow-inset),
      var(--px-shadow);
    transition:
      background var(--px-transition),
      border-color var(--px-transition),
      box-shadow var(--px-transition);
  }

  .header-inner {
    display: flex;
    align-items: center;
    height: var(--px-header-height, 64px);
    max-width: var(--px-layout-max-width);
    margin: 0 auto;
    padding: 0 1.5rem;
    gap: 1.5rem;
  }

  /* ── Logo ── */
  .logo {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    color: var(--px-text);
    text-decoration: none;
    flex-shrink: 0;
  }

  .logo:hover {
    text-decoration: none;
    color: var(--px-text);
  }

  .logo img {
    border: none;
    box-shadow: none;
    border-radius: 0;
  }

  /* Invert the white logo in light mode so it's visible on glass */
  :global(:root:not([data-theme="dark"])) .logo img {
    filter: brightness(0) saturate(100%) invert(15%) sepia(60%) saturate(3000%) hue-rotate(290deg) brightness(70%);
  }

  .logo-text {
    font-family: var(--px-font-heading);
    font-weight: 700;
    font-size: 1.25rem;
    letter-spacing: -0.03em;
  }

  .logo-badge {
    font-family: var(--px-font-ui);
    font-size: 0.6rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    background: var(--px-accent);
    padding: 0.2rem 0.5rem;
    border-radius: 9999px;
    color: white;
    box-shadow: 0 0 12px rgba(240, 108, 186, 0.3);
  }

  /* ── Desktop nav ── */
  .nav-desktop {
    display: flex;
    align-items: center;
    gap: 0.25rem;
    margin-left: 1rem;
  }

  .nav-link {
    font-family: var(--px-font-ui);
    color: var(--px-text-secondary);
    text-decoration: none;
    font-size: 0.8rem;
    font-weight: 500;
    padding: 0.4rem 0.85rem;
    border-radius: var(--px-radius);
    transition:
      all 200ms ease,
      box-shadow 200ms ease;
    white-space: nowrap;
    letter-spacing: -0.01em;
  }

  .nav-link:hover {
    color: var(--px-text);
    background: var(--px-bg-elevated);
    text-decoration: none;
    text-shadow: none;
    box-shadow: var(--px-glow-accent);
  }

  .nav-link.active {
    color: var(--px-accent);
    background: var(--px-bg-elevated);
    box-shadow:
      inset 0 -2px 0 var(--px-accent),
      0 0 12px rgba(240, 108, 186, 0.15);
  }

  /* ── Actions ── */
  .header-actions {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin-left: auto;
  }

  /* ── Search trigger ── */
  .search-trigger {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.4rem 0.75rem;
    background: var(--px-bg-elevated);
    border: 1px solid var(--px-glass-border);
    border-radius: var(--px-radius);
    color: var(--px-text-muted);
    cursor: pointer;
    font-family: var(--px-font-ui);
    font-size: 0.75rem;
    transition:
      all 200ms ease,
      box-shadow 200ms ease;
    white-space: nowrap;
  }

  .search-trigger:hover {
    color: var(--px-text);
    border-color: var(--px-accent);
    box-shadow: var(--px-glow-accent);
  }

  .search-label {
    display: none;
  }

  .search-kbd {
    display: none;
    font-family: var(--px-font-ui);
    font-size: 0.65rem;
    padding: 0.1rem 0.35rem;
    border-radius: 0.25rem;
    background: var(--px-bg-alt);
    border: 1px solid var(--px-border);
    color: var(--px-text-muted);
    line-height: 1.4;
  }

  @media (min-width: 768px) {
    .search-label {
      display: inline;
    }
    .search-kbd {
      display: inline;
    }
  }

  /* ── Icon button ── */
  .icon-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 36px;
    height: 36px;
    border-radius: var(--px-radius);
    color: var(--px-text-muted);
    transition:
      all 200ms ease,
      box-shadow 200ms ease;
    text-decoration: none;
  }

  .icon-btn:hover {
    color: var(--px-text);
    background: var(--px-bg-elevated);
    text-decoration: none;
    box-shadow: var(--px-glow-accent);
    text-shadow: none;
  }

  /* ── Mobile menu button ── */
  .mobile-menu-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 36px;
    height: 36px;
    border: none;
    background: none;
    color: var(--px-text-secondary);
    cursor: pointer;
    border-radius: var(--px-radius);
    transition: all 200ms ease;
  }

  .mobile-menu-btn:hover {
    background: var(--px-bg-elevated);
    color: var(--px-text);
  }

  @media (min-width: 1024px) {
    .mobile-menu-btn {
      display: none;
    }
  }

  @media (max-width: 1023px) {
    .nav-desktop {
      display: none;
    }
  }

  /* ── Mobile nav ── */
  .nav-mobile {
    display: flex;
    flex-direction: column;
    padding: 0.5rem 1rem 1rem;
    border-top: 1px solid var(--px-glass-border);
  }

  .nav-mobile-link {
    font-family: var(--px-font-ui);
    color: var(--px-text-secondary);
    text-decoration: none;
    font-size: 0.85rem;
    font-weight: 500;
    padding: 0.6rem 0.75rem;
    border-radius: var(--px-radius);
    transition: all 200ms ease;
  }

  .nav-mobile-link:hover,
  .nav-mobile-link.active {
    color: var(--px-accent);
    background: var(--px-bg-elevated);
    text-decoration: none;
    text-shadow: none;
  }

  /* ── Mobile: full-width header ── */
  @media (max-width: 768px) {
    .header {
      margin: 0.5rem 0.75rem 0;
      border-radius: var(--px-radius-lg);
    }
  }
</style>
