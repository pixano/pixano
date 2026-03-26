<script lang="ts">
	import { onMount } from 'svelte';
	import Konva from 'konva';

	interface Props {
		widgetId: string;
		options: Record<string, unknown>;
		data?: Record<string, unknown>;
	}

	let { widgetId, options, data }: Props = $props();

	let containerEl = $state<HTMLDivElement>(null!);
	let stage = $state<Konva.Stage | null>(null);
	let imageLoaded = $state(false);
	let imageError = $state(false);

	onMount(() => {
		if (!containerEl) return;

		const { width, height } = containerEl.getBoundingClientRect();

		stage = new Konva.Stage({
			container: containerEl,
			width: width || 400,
			height: height || 300
		});

		const layer = new Konva.Layer();
		stage.add(layer);

		// Load image if URL provided
		const imageUrl = data?.imageUrl as string | undefined;
		if (imageUrl) {
			const img = new Image();
			img.onload = () => {
				if (!stage) return;

				const konvaImage = new Konva.Image({
					image: img,
					x: 0,
					y: 0,
					width: stage.width(),
					height: stage.height()
				});

				// Fit image to canvas maintaining aspect ratio
				const scaleX = stage.width() / img.width;
				const scaleY = stage.height() / img.height;
				const scale = Math.min(scaleX, scaleY);

				konvaImage.width(img.width * scale);
				konvaImage.height(img.height * scale);
				konvaImage.x((stage.width() - konvaImage.width()) / 2);
				konvaImage.y((stage.height() - konvaImage.height()) / 2);

				layer.add(konvaImage);
				layer.draw();
				imageLoaded = true;
			};
			img.onerror = () => {
				imageError = true;
			};
			img.src = imageUrl;
		} else {
			// Draw placeholder grid pattern
			drawPlaceholder(layer, stage.width(), stage.height());
		}

		// ResizeObserver for responsive sizing
		const resizeObserver = new ResizeObserver((entries) => {
			for (const entry of entries) {
				const { width: w, height: h } = entry.contentRect;
				if (stage && w > 0 && h > 0) {
					stage.width(w);
					stage.height(h);
					stage.draw();
				}
			}
		});

		resizeObserver.observe(containerEl);

		return () => {
			resizeObserver.disconnect();
			stage?.destroy();
			stage = null;
		};
	});

	function drawPlaceholder(layer: Konva.Layer, width: number, height: number) {
		// Draw a grid pattern as placeholder
		const gridSize = 30;
		for (let x = 0; x < width; x += gridSize) {
			layer.add(
				new Konva.Line({
					points: [x, 0, x, height],
					stroke: 'rgba(255,255,255,0.05)',
					strokeWidth: 1
				})
			);
		}
		for (let y = 0; y < height; y += gridSize) {
			layer.add(
				new Konva.Line({
					points: [0, y, width, y],
					stroke: 'rgba(255,255,255,0.05)',
					strokeWidth: 1
				})
			);
		}

		// Center text
		layer.add(
			new Konva.Text({
				text: 'Image Canvas',
				x: 0,
				y: height / 2 - 12,
				width: width,
				align: 'center',
				fontSize: 16,
				fill: 'rgba(255,255,255,0.3)',
				fontFamily: 'system-ui, sans-serif'
			})
		);

		layer.draw();
	}
</script>

<div class="flex h-full flex-col bg-card">
	{#if imageError}
		<div class="flex flex-1 items-center justify-center">
			<div class="text-center text-muted-foreground">
				<div class="mb-1 text-sm">Failed to load image</div>
				<div class="text-xs">{data?.imageUrl}</div>
			</div>
		</div>
	{:else}
		<div bind:this={containerEl} class="flex-1" style="min-height: 100px;"></div>
	{/if}
</div>
