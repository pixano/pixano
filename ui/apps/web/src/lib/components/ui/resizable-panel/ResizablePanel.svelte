<script lang="ts">
	import type { Snippet } from 'svelte';
	import type { PanelState } from './PanelState.svelte.js';

	interface Props {
		state: PanelState;
		side: 'left' | 'right';
		children: Snippet;
	}

	let { state, side, children }: Props = $props();

	let startX = 0;
	let startWidth = 0;

	function onPointerDown(e: PointerEvent) {
		e.preventDefault();
		state.isDragging = true;
		startX = e.clientX;
		startWidth = state.width;

		window.addEventListener('pointermove', onPointerMove);
		window.addEventListener('pointerup', onPointerUp);
	}

	function onPointerMove(e: PointerEvent) {
		const delta = e.clientX - startX;
		const newWidth = side === 'left' ? startWidth + delta : startWidth - delta;
		state.setWidth(newWidth);
	}

	function onPointerUp() {
		state.isDragging = false;
		window.removeEventListener('pointermove', onPointerMove);
		window.removeEventListener('pointerup', onPointerUp);
	}

	function onHandleDoubleClick() {
		state.toggle();
	}

	let panelStyle = $derived(
		state.collapsed
			? 'width: 0px;'
			: `width: ${state.width}px;`
	);

	let transitionClass = $derived(
		state.isDragging ? '' : 'transition-[width] duration-200 ease-in-out'
	);
</script>

{#if side === 'left'}
	<div
		class="relative flex-shrink-0 overflow-hidden border-r border-border {transitionClass}"
		style={panelStyle}
	>
		<div class="h-full overflow-hidden" style="width: {state.collapsed ? 0 : state.width}px;">
			{@render children()}
		</div>
	</div>
	<!-- Drag handle -->
	<div
		class="group relative z-10 flex w-1 flex-shrink-0 cursor-col-resize items-center justify-center hover:bg-primary/20"
		onpointerdown={onPointerDown}
		ondblclick={onHandleDoubleClick}
		role="separator"
		aria-orientation="vertical"
	>
		<div class="h-8 w-0.5 rounded-full bg-border transition-colors group-hover:bg-primary"></div>
	</div>
{:else}
	<!-- Drag handle -->
	<div
		class="group relative z-10 flex w-1 flex-shrink-0 cursor-col-resize items-center justify-center hover:bg-primary/20"
		onpointerdown={onPointerDown}
		ondblclick={onHandleDoubleClick}
		role="separator"
		aria-orientation="vertical"
	>
		<div class="h-8 w-0.5 rounded-full bg-border transition-colors group-hover:bg-primary"></div>
	</div>
	<div
		class="relative flex-shrink-0 overflow-hidden border-l border-border {transitionClass}"
		style={panelStyle}
	>
		<div class="h-full overflow-hidden" style="width: {state.collapsed ? 0 : state.width}px;">
			{@render children()}
		</div>
	</div>
{/if}

{#if state.isDragging}
	<!-- Overlay to prevent iframe/canvas stealing pointer events during drag -->
	<div class="fixed inset-0 z-50 cursor-col-resize" style="user-select: none;"></div>
{/if}
