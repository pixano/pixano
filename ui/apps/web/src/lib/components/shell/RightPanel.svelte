<script lang="ts">
	import type { WorkspaceManager } from '$lib/workspace/workspaceManager.svelte.js';
	import { ScanSearch, MessageSquare } from 'lucide-svelte';

	interface Props {
		manager: WorkspaceManager;
	}

	let { manager }: Props = $props();

	let activeTab = $state<'inspector' | 'agent'>('inspector');

	const tabs = [
		{ id: 'inspector' as const, label: 'Inspector', icon: ScanSearch },
		{ id: 'agent' as const, label: 'Agent', icon: MessageSquare }
	];
</script>

<div class="flex h-full flex-col bg-background">
	<!-- Tab bar -->
	<div class="flex h-10 items-center border-b border-border">
		{#each tabs as tab (tab.id)}
			{@const Icon = tab.icon}
			<button
				onclick={() => (activeTab = tab.id)}
				class="flex h-full flex-1 items-center justify-center gap-1.5 text-xs font-medium transition-colors
					{activeTab === tab.id
					? 'border-b-2 border-primary text-foreground'
					: 'text-muted-foreground hover:text-foreground'}"
			>
				<Icon class="h-3.5 w-3.5" />
				{tab.label}
			</button>
		{/each}
	</div>

	<!-- Tab content -->
	<div class="flex-1 overflow-y-auto">
		{#if activeTab === 'inspector'}
			<div class="p-3">
				<h4 class="mb-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
					Properties
				</h4>

				{#if manager.widgetCount > 0}
					<div class="space-y-2">
						{#each manager.widgets as widget (widget.id)}
							<div class="rounded-md border border-border bg-card p-2">
								<div class="flex items-center justify-between">
									<span class="text-xs font-medium text-card-foreground">{widget.title}</span>
									<span class="rounded bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground">
										{widget.extensionName}
									</span>
								</div>
								<div class="mt-1.5 grid grid-cols-2 gap-1 text-[10px] text-muted-foreground">
									<span>x: {widget.layout.x}</span>
									<span>y: {widget.layout.y}</span>
									<span>w: {widget.layout.w}</span>
									<span>h: {widget.layout.h}</span>
								</div>
							</div>
						{/each}
					</div>
				{:else}
					<p class="text-xs text-muted-foreground">No widgets in workspace.</p>
				{/if}
			</div>
		{:else if activeTab === 'agent'}
			<div class="flex h-full flex-col">
				<!-- Chat messages -->
				<div class="flex-1 p-3">
					<div class="flex flex-col gap-3">
						<div class="rounded-lg bg-muted/50 px-3 py-2">
							<p class="text-xs text-muted-foreground">
								AI Agent ready. Ask questions about your dataset or request annotations.
							</p>
						</div>
					</div>
				</div>

				<!-- Chat input -->
				<div class="border-t border-border p-2">
					<div class="flex gap-2">
						<input
							type="text"
							placeholder="Ask the agent..."
							class="flex-1 rounded-md border border-input bg-muted/50 px-3 py-1.5 text-xs text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring"
						/>
						<button
							class="rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground hover:bg-primary/90"
						>
							Send
						</button>
					</div>
				</div>
			</div>
		{/if}
	</div>
</div>
