import { WidgetExtension } from '../WidgetExtension.js';
import PointCloudWidget from '$lib/components/widgets/PointCloudWidget.svelte';

export const PointCloudExtension = WidgetExtension.create({
	name: 'point-cloud',
	label: '3D Viewer',
	icon: 'box',
	priority: 90,
	defaultLayout: { x: 6, y: 0, w: 6, h: 5, minW: 3, minH: 3 },
	component: PointCloudWidget,
	addOptions: () => ({
		pointSize: 0.08,
		backgroundColor: '#1e293b'
	})
});
