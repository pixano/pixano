import type { WorkspacePreset } from '$lib/extensions/types.js';

export const DEFAULT_PRESET: WorkspacePreset = {
	name: 'Default',
	widgets: [
		{
			extensionName: 'image',
			title: '2D Canvas',
			layout: { x: 0, y: 0, w: 5, h: 5 },
			options: {},
			data: { imageUrl: '/sample-image.svg' }
		},
		{
			extensionName: 'text',
			title: 'Rich Text',
			layout: { x: 5, y: 0, w: 4, h: 5 },
			options: {},
			data: {
				content:
					'<h2>Annotation Notes</h2><p>This is a <strong>rich text editor</strong> powered by TipTap.</p><p>Use it to add notes, descriptions, or metadata to your dataset samples.</p><ul><li>Bold, italic, strikethrough</li><li>Headings and lists</li><li>Code blocks and quotes</li></ul>'
			}
		},
		{
			extensionName: 'point-cloud',
			title: '3D Viewer',
			layout: { x: 9, y: 0, w: 3, h: 5 },
			options: {},
			data: {}
		}
	]
};

export const PRESETS: WorkspacePreset[] = [DEFAULT_PRESET];
