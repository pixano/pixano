import { WidgetExtension } from '../WidgetExtension.js';
import TextWidget from '$lib/components/widgets/TextWidget.svelte';

export const TextExtension = WidgetExtension.create({
	name: 'text',
	label: 'Rich Text',
	icon: 'file-text',
	priority: 80,
	defaultLayout: { x: 0, y: 0, w: 4, h: 4, minW: 2, minH: 2 },
	component: TextWidget,
	addOptions: () => ({
		editable: true
	}),
	addStorage: () => ({
		editorInstance: null
	})
});
