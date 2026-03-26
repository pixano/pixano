import { WidgetExtension } from '../WidgetExtension.js';
import ImageWidget from '$lib/components/widgets/ImageWidget.svelte';

export const ImageExtension = WidgetExtension.create({
	name: 'image',
	label: '2D Canvas',
	icon: 'image',
	priority: 100,
	defaultLayout: { x: 0, y: 0, w: 6, h: 5, minW: 3, minH: 3 },
	component: ImageWidget,
	addOptions: () => ({
		imageUrl: '/sample-image.svg',
		tools: ['select', 'bbox']
	})
});
