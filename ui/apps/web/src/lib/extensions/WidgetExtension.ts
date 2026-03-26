import type { WidgetExtensionConfig } from './types.js';

/**
 * Factory class for creating widget extensions.
 * Mirrors TipTap's Extension.create() / .configure() / .extend() pattern.
 */
export class WidgetExtension<
	TOptions extends Record<string, unknown> = Record<string, unknown>,
	TStorage extends Record<string, unknown> = Record<string, unknown>
> {
	readonly config: WidgetExtensionConfig<TOptions, TStorage>;

	private constructor(config: WidgetExtensionConfig<TOptions, TStorage>) {
		this.config = config;
	}

	/** Create a new widget extension from a config object */
	static create<
		TOptions extends Record<string, unknown> = Record<string, unknown>,
		TStorage extends Record<string, unknown> = Record<string, unknown>
	>(config: WidgetExtensionConfig<TOptions, TStorage>): WidgetExtension<TOptions, TStorage> {
		return new WidgetExtension(config);
	}

	/** Returns a new extension with merged options (like TipTap's .configure()) */
	configure(options: Partial<TOptions>): WidgetExtension<TOptions, TStorage> {
		const parentAddOptions = this.config.addOptions;
		return new WidgetExtension({
			...this.config,
			addOptions: () => ({
				...(parentAddOptions?.() ?? ({} as TOptions)),
				...options
			})
		});
	}

	/** Returns a new extension with overridden config fields (like TipTap's .extend()) */
	extend(
		overrides: Partial<WidgetExtensionConfig<TOptions, TStorage>>
	): WidgetExtension<TOptions, TStorage> {
		return new WidgetExtension({
			...this.config,
			...overrides
		});
	}
}
