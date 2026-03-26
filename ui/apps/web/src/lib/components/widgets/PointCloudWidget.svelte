<script lang="ts">
	import { onMount } from 'svelte';
	import type { Component } from 'svelte';

	interface Props {
		widgetId: string;
		options: Record<string, unknown>;
		data?: Record<string, unknown>;
	}

	let { widgetId, options, data }: Props = $props();

	let ready = $state(false);
	let error = $state<string | null>(null);
	// eslint-disable-next-line @typescript-eslint/no-explicit-any
	let CanvasComponent = $state<Component<any> | null>(null);
	// eslint-disable-next-line @typescript-eslint/no-explicit-any
	let SceneComponent = $state<Component<any> | null>(null);

	onMount(async () => {
		try {
			const [threlte, scene] = await Promise.all([
				import('@threlte/core'),
				import('./PointCloudScene.svelte')
			]);
			CanvasComponent = threlte.Canvas;
			SceneComponent = scene.default;
			ready = true;
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to load 3D viewer';
			console.error('PointCloudWidget init error:', e);
		}
	});
</script>

<div class="relative h-full w-full bg-card">
	{#if error}
		<div class="flex h-full items-center justify-center">
			<div class="text-center text-muted-foreground">
				<div class="mb-1 text-sm">3D Viewer Error</div>
				<div class="text-xs">{error}</div>
			</div>
		</div>
	{:else if ready && CanvasComponent && SceneComponent}
		<div class="absolute inset-0">
			<CanvasComponent>
				<SceneComponent />
			</CanvasComponent>
		</div>
	{:else}
		<div class="flex h-full items-center justify-center">
			<div class="text-xs text-muted-foreground">Loading 3D viewer...</div>
		</div>
	{/if}
</div>
