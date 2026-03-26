/**
 * Reactive state for a resizable panel.
 * Uses Svelte 5 $state runes for fine-grained reactivity.
 */
export class PanelState {
	width = $state(280);
	collapsed = $state(false);
	isDragging = $state(false);

	readonly minWidth: number;
	readonly maxWidth: number;
	readonly defaultWidth: number;

	constructor(opts?: { defaultWidth?: number; minWidth?: number; maxWidth?: number }) {
		this.defaultWidth = opts?.defaultWidth ?? 280;
		this.minWidth = opts?.minWidth ?? 200;
		this.maxWidth = opts?.maxWidth ?? 480;
		this.width = this.defaultWidth;
	}

	toggle() {
		this.collapsed = !this.collapsed;
	}

	setWidth(w: number) {
		this.width = Math.min(this.maxWidth, Math.max(this.minWidth, w));
	}
}
