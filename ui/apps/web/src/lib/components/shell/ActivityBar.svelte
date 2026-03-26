<script lang="ts">
	import { FolderOpen, LayoutGrid, Search, Settings } from 'lucide-svelte';

	interface Props {
		activeSection: string;
		onSectionChange: (section: string) => void;
		onSettingsClick?: () => void;
	}

	let { activeSection, onSectionChange, onSettingsClick }: Props = $props();

	const navItems = [
		{ id: 'explorer', icon: FolderOpen, label: 'Explorer' },
		{ id: 'widgets', icon: LayoutGrid, label: 'Widgets' },
		{ id: 'search', icon: Search, label: 'Search' }
	] as const;
</script>

<div
	class="flex w-12 flex-shrink-0 flex-col items-center border-r border-border bg-background"
>
	<!-- Logo -->
	<div class="flex h-10 w-full items-center justify-center border-b border-border">
		<div
			class="flex h-6 w-6 items-center justify-center rounded-md bg-primary text-primary-foreground"
		>
			<span class="text-[10px] font-bold leading-none">P</span>
		</div>
	</div>

	<!-- Nav icons -->
	<div class="flex flex-1 flex-col items-center gap-0.5 pt-1">
		{#each navItems as item (item.id)}
			{@const Icon = item.icon}
			{@const isActive = activeSection === item.id}
			<button
				onclick={() => onSectionChange(item.id)}
				class="relative flex h-10 w-10 items-center justify-center rounded-md transition-colors
					{isActive
					? 'text-foreground'
					: 'text-muted-foreground hover:text-foreground'}"
				title={item.label}
			>
				{#if isActive}
					<div
						class="absolute left-0 top-1/2 h-5 w-0.5 -translate-y-1/2 rounded-r-full bg-primary"
					></div>
				{/if}
				<Icon class="h-5 w-5" />
			</button>
		{/each}
	</div>

	<!-- Bottom section -->
	<div class="flex flex-col items-center gap-0.5 pb-2">
		<button
			onclick={() => onSettingsClick?.()}
			class="flex h-10 w-10 items-center justify-center rounded-md text-muted-foreground transition-colors hover:text-foreground"
			title="Settings"
		>
			<Settings class="h-5 w-5" />
		</button>
	</div>
</div>
