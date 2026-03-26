import type { WidgetExtensionConfig } from './types.js';
import type { WidgetExtension } from './WidgetExtension.js';

/**
 * Registry that holds all available widget extension configs.
 * Extensions are registered once and looked up by name when creating widget instances.
 */
export class WidgetRegistry {
	private extensions: Map<string, WidgetExtensionConfig> = new Map();

	/** Register a widget extension. Also registers any bundled child extensions. */
	// eslint-disable-next-line @typescript-eslint/no-explicit-any
	register(extension: WidgetExtension<any, any>): void {
		const config = extension.config;
		if (this.extensions.has(config.name)) {
			console.warn(
				`Widget extension "${config.name}" is already registered. Overwriting.`
			);
		}
		this.extensions.set(config.name, config);

		// Register bundled child extensions
		const children = config.addExtensions?.();
		if (children) {
			for (const child of children) {
				this.extensions.set(child.name, child);
			}
		}
	}

	/** Get an extension config by name */
	get(name: string): WidgetExtensionConfig | undefined {
		return this.extensions.get(name);
	}

	/** Get all registered extensions, sorted by priority (highest first) */
	getAll(): WidgetExtensionConfig[] {
		return Array.from(this.extensions.values()).sort(
			(a, b) => (b.priority ?? 0) - (a.priority ?? 0)
		);
	}

	/** Check if an extension is registered */
	has(name: string): boolean {
		return this.extensions.has(name);
	}
}
