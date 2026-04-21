<!-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------->

<script lang="ts">
  import Konva from "konva";
  import { onMount } from "svelte";

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

  let layer: Konva.Layer | null = null;
  let konvaImage: Konva.Image | null = null;
  let loadedImg: HTMLImageElement | null = null;
  let placeholderShapes: Konva.Node[] = [];

  function fitImageToStage() {
    if (!stage || !konvaImage || !loadedImg) return;
    const sw = stage.width();
    const sh = stage.height();
    const scale = Math.min(sw / loadedImg.width, sh / loadedImg.height);
    const iw = loadedImg.width * scale;
    const ih = loadedImg.height * scale;
    konvaImage.width(iw);
    konvaImage.height(ih);
    konvaImage.x((sw - iw) / 2);
    konvaImage.y((sh - ih) / 2);
    layer?.batchDraw();
  }

  function redrawPlaceholder() {
    if (!stage || !layer) return;
    for (const node of placeholderShapes) node.destroy();
    placeholderShapes = [];
    drawPlaceholder(layer, stage.width(), stage.height());
  }

  onMount(() => {
    if (!containerEl) return;

    const { width, height } = containerEl.getBoundingClientRect();

    stage = new Konva.Stage({
      container: containerEl,
      width: width || 400,
      height: height || 300,
    });

    layer = new Konva.Layer();
    stage.add(layer);

    const imageUrl = data?.imageUrl as string | undefined;
    if (imageUrl) {
      const img = new Image();
      img.onload = () => {
        if (!stage || !layer) return;
        loadedImg = img;
        konvaImage = new Konva.Image({ image: img, x: 0, y: 0 });
        layer.add(konvaImage);
        fitImageToStage();
        imageLoaded = true;
      };
      img.onerror = () => {
        imageError = true;
      };
      img.src = imageUrl;
    } else {
      drawPlaceholder(layer, stage.width(), stage.height());
    }

    // Rescale image/placeholder whenever the widget (and thus the stage) is resized.
    const resizeObserver = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const { width: w, height: h } = entry.contentRect;
        if (stage && w > 0 && h > 0) {
          stage.width(w);
          stage.height(h);
          if (konvaImage) {
            fitImageToStage();
          } else if (!imageUrl) {
            redrawPlaceholder();
          }
          stage.draw();
        }
      }
    });

    resizeObserver.observe(containerEl);

    return () => {
      resizeObserver.disconnect();
      stage?.destroy();
      stage = null;
      layer = null;
      konvaImage = null;
      loadedImg = null;
      placeholderShapes = [];
    };
  });

  function drawPlaceholder(layer: Konva.Layer, width: number, height: number) {
    const gridSize = 30;
    const add = (node: Konva.Node) => {
      layer.add(node as Konva.Shape);
      placeholderShapes.push(node);
    };

    for (let x = 0; x < width; x += gridSize) {
      add(
        new Konva.Line({
          points: [x, 0, x, height],
          stroke: "rgba(255,255,255,0.05)",
          strokeWidth: 1,
        }),
      );
    }
    for (let y = 0; y < height; y += gridSize) {
      add(
        new Konva.Line({
          points: [0, y, width, y],
          stroke: "rgba(255,255,255,0.05)",
          strokeWidth: 1,
        }),
      );
    }

    add(
      new Konva.Text({
        text: "Image Canvas",
        x: 0,
        y: height / 2 - 12,
        width: width,
        align: "center",
        fontSize: 16,
        fill: "rgba(255,255,255,0.3)",
        fontFamily: "system-ui, sans-serif",
      }),
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
