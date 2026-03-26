import { WidgetRegistry } from '../WidgetRegistry.js';
import { ImageExtension } from './ImageExtension.js';
import { TextExtension } from './TextExtension.js';
import { PointCloudExtension } from './PointCloudExtension.js';

export function createDefaultRegistry(): WidgetRegistry {
	const registry = new WidgetRegistry();
	registry.register(ImageExtension);
	registry.register(TextExtension);
	registry.register(PointCloudExtension);
	return registry;
}

export { ImageExtension, TextExtension, PointCloudExtension };
