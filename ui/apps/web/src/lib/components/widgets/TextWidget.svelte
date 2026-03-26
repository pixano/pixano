<script lang="ts">
	import { onMount, onDestroy } from 'svelte';
	import { Editor } from '@tiptap/core';
	import { Color } from '@tiptap/extension-color';
	import ListItem from '@tiptap/extension-list-item';
	import { TextStyle } from '@tiptap/extension-text-style';
	import StarterKit from '@tiptap/starter-kit';

	interface Props {
		widgetId: string;
		options: Record<string, unknown>;
		data?: Record<string, unknown>;
	}

	let { widgetId, options, data }: Props = $props();

	let editor = $state<Editor | null>(null);
	let element = $state<HTMLElement>(null!);
	let hasContent = $derived(!!data?.content);

	onMount(() => {
		if (!data?.content) return;

		editor = new Editor({
			element: element,
			extensions: [
				Color.configure({ types: [TextStyle.name, ListItem.name] }),
				TextStyle,
				StarterKit
			],
			content: (data?.content as string) || '',
			editorProps: {
				attributes: {
					class: 'prose prose-sm prose-invert max-w-none p-4 focus:outline-none min-h-full'
				}
			},
			onTransaction: () => {
				editor = editor;
			}
		});
	});

	onDestroy(() => {
		editor?.destroy();
	});
</script>

<div class="flex h-full flex-col overflow-hidden bg-card">
	{#if editor && hasContent}
		<div class="border-b border-border bg-muted/50 p-1.5">
			<div class="flex flex-wrap gap-0.5">
				<button
					onclick={() => editor?.chain().focus().toggleBold().run()}
					disabled={!editor?.can().chain().focus().toggleBold().run()}
					class="rounded px-2 py-0.5 text-xs font-medium text-muted-foreground hover:bg-accent hover:text-accent-foreground disabled:opacity-40 {editor?.isActive(
						'bold'
					)
						? 'bg-accent text-accent-foreground'
						: ''}"
				>
					B
				</button>
				<button
					onclick={() => editor?.chain().focus().toggleItalic().run()}
					disabled={!editor?.can().chain().focus().toggleItalic().run()}
					class="rounded px-2 py-0.5 text-xs italic text-muted-foreground hover:bg-accent hover:text-accent-foreground disabled:opacity-40 {editor?.isActive(
						'italic'
					)
						? 'bg-accent text-accent-foreground'
						: ''}"
				>
					I
				</button>
				<button
					onclick={() => editor?.chain().focus().toggleStrike().run()}
					disabled={!editor?.can().chain().focus().toggleStrike().run()}
					class="rounded px-2 py-0.5 text-xs text-muted-foreground line-through hover:bg-accent hover:text-accent-foreground disabled:opacity-40 {editor?.isActive(
						'strike'
					)
						? 'bg-accent text-accent-foreground'
						: ''}"
				>
					S
				</button>
				<span class="mx-1 w-px bg-border"></span>
				<button
					onclick={() => editor?.chain().focus().toggleHeading({ level: 1 }).run()}
					class="rounded px-2 py-0.5 text-xs text-muted-foreground hover:bg-accent hover:text-accent-foreground {editor?.isActive(
						'heading',
						{ level: 1 }
					)
						? 'bg-accent text-accent-foreground'
						: ''}"
				>
					H1
				</button>
				<button
					onclick={() => editor?.chain().focus().toggleHeading({ level: 2 }).run()}
					class="rounded px-2 py-0.5 text-xs text-muted-foreground hover:bg-accent hover:text-accent-foreground {editor?.isActive(
						'heading',
						{ level: 2 }
					)
						? 'bg-accent text-accent-foreground'
						: ''}"
				>
					H2
				</button>
				<button
					onclick={() => editor?.chain().focus().toggleHeading({ level: 3 }).run()}
					class="rounded px-2 py-0.5 text-xs text-muted-foreground hover:bg-accent hover:text-accent-foreground {editor?.isActive(
						'heading',
						{ level: 3 }
					)
						? 'bg-accent text-accent-foreground'
						: ''}"
				>
					H3
				</button>
				<span class="mx-1 w-px bg-border"></span>
				<button
					onclick={() => editor?.chain().focus().toggleBulletList().run()}
					class="rounded px-2 py-0.5 text-xs text-muted-foreground hover:bg-accent hover:text-accent-foreground {editor?.isActive(
						'bulletList'
					)
						? 'bg-accent text-accent-foreground'
						: ''}"
				>
					List
				</button>
				<button
					onclick={() => editor?.chain().focus().toggleCodeBlock().run()}
					class="rounded px-2 py-0.5 text-xs font-mono text-muted-foreground hover:bg-accent hover:text-accent-foreground {editor?.isActive(
						'codeBlock'
					)
						? 'bg-accent text-accent-foreground'
						: ''}"
				>
					{'</>'}
				</button>
				<button
					onclick={() => editor?.chain().focus().toggleBlockquote().run()}
					class="rounded px-2 py-0.5 text-xs text-muted-foreground hover:bg-accent hover:text-accent-foreground {editor?.isActive(
						'blockquote'
					)
						? 'bg-accent text-accent-foreground'
						: ''}"
				>
					Quote
				</button>
				<span class="mx-1 w-px bg-border"></span>
				<button
					onclick={() => editor?.chain().focus().undo().run()}
					disabled={!editor?.can().chain().focus().undo().run()}
					class="rounded px-2 py-0.5 text-xs text-muted-foreground hover:bg-accent hover:text-accent-foreground disabled:opacity-40"
				>
					Undo
				</button>
				<button
					onclick={() => editor?.chain().focus().redo().run()}
					disabled={!editor?.can().chain().focus().redo().run()}
					class="rounded px-2 py-0.5 text-xs text-muted-foreground hover:bg-accent hover:text-accent-foreground disabled:opacity-40"
				>
					Redo
				</button>
			</div>
		</div>
	{/if}

	<div class="flex min-h-0 flex-1 flex-col">
		{#if hasContent}
			<div bind:this={element} class="flex-1 overflow-y-auto bg-card"></div>
		{:else}
			<div class="flex flex-1 items-center justify-center">
				<div class="text-center text-muted-foreground">
					<div class="mb-1 text-sm">No Text Data</div>
					<div class="text-xs">No text content available</div>
				</div>
			</div>
		{/if}
	</div>
</div>

<style>
	:global(.ProseMirror) {
		height: 100%;
		outline: none;
	}

	:global(.ProseMirror h1) {
		font-size: 1.5rem;
		font-weight: 700;
		margin-bottom: 1rem;
		margin-top: 1.5rem;
	}

	:global(.ProseMirror h1:first-child) {
		margin-top: 0;
	}

	:global(.ProseMirror h2) {
		font-size: 1.25rem;
		font-weight: 600;
		margin-bottom: 0.75rem;
		margin-top: 1.25rem;
	}

	:global(.ProseMirror h3) {
		font-size: 1.125rem;
		font-weight: 500;
		margin-bottom: 0.5rem;
		margin-top: 1rem;
	}

	:global(.ProseMirror p) {
		margin-bottom: 0.75rem;
		line-height: 1.625;
	}

	:global(.ProseMirror ul, .ProseMirror ol) {
		margin-bottom: 0.75rem;
		margin-left: 1.5rem;
	}

	:global(.ProseMirror ul) {
		list-style-type: disc;
	}

	:global(.ProseMirror ol) {
		list-style-type: decimal;
	}

	:global(.ProseMirror li) {
		margin-bottom: 0.25rem;
	}

	:global(.ProseMirror blockquote) {
		border-left: 4px solid oklch(0.4 0 0);
		padding-left: 1rem;
		font-style: italic;
		color: oklch(0.65 0 0);
		margin-top: 1rem;
		margin-bottom: 1rem;
	}

	:global(.ProseMirror hr) {
		border-top: 1px solid oklch(0.3 0 0);
		margin-top: 1.5rem;
		margin-bottom: 1.5rem;
	}

	:global(.ProseMirror code) {
		background-color: oklch(0.25 0 0);
		color: oklch(0.85 0 0);
		padding: 0.125rem 0.25rem;
		border-radius: 0.25rem;
		font-size: 0.875rem;
		font-family:
			ui-monospace,
			SFMono-Regular,
			'SF Mono',
			Consolas,
			'Liberation Mono',
			Menlo,
			monospace;
	}

	:global(.ProseMirror pre) {
		background-color: oklch(0.2 0 0);
		padding: 1rem;
		border-radius: 0.25rem;
		overflow-x: auto;
		margin-top: 1rem;
		margin-bottom: 1rem;
	}

	:global(.ProseMirror pre code) {
		background-color: transparent;
		padding: 0;
	}
</style>
