/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

const BOUNDARY = "frame_boundary";
const HEADER_SEPARATOR = "\r\n\r\n";
const CR = 0x0d;
const LF = 0x0a;
const DASH = 0x2d;

const textEncoder = new TextEncoder();
const textDecoder = new TextDecoder();
type AnyBytes = Uint8Array<ArrayBufferLike>;

export type StreamedFramePart = {
  frameIndex: number;
  contentType: string;
  blob: Blob;
};

function parseBoundary(contentType: string | null): string {
  if (!contentType) return BOUNDARY;
  const match = contentType.match(/boundary=([^;]+)/i);
  if (!match) return BOUNDARY;
  return match[1].trim().replace(/^"|"$/g, "") || BOUNDARY;
}

function concatBytes(left: AnyBytes, right: AnyBytes): AnyBytes {
  if (left.length === 0) return right;
  if (right.length === 0) return left;
  const out = new Uint8Array(left.length + right.length);
  out.set(left, 0);
  out.set(right, left.length);
  return out;
}

function indexOfBytes(haystack: AnyBytes, needle: AnyBytes, from = 0): number {
  if (needle.length === 0) return from;
  outer: for (let i = from; i <= haystack.length - needle.length; i++) {
    for (let j = 0; j < needle.length; j++) {
      if (haystack[i + j] !== needle[j]) continue outer;
    }
    return i;
  }
  return -1;
}

function parseHeaders(headersBlock: string): Map<string, string> {
  const headers = new Map<string, string>();
  for (const line of headersBlock.split("\r\n")) {
    const split = line.indexOf(":");
    if (split === -1) continue;
    headers.set(line.slice(0, split).trim().toLowerCase(), line.slice(split + 1).trim());
  }
  return headers;
}

/**
 * Stream multipart frame parts progressively.
 *
 * The parser is content-length driven, so we can extract each frame as soon as
 * its bytes arrive without buffering the whole response in memory.
 */
export async function* streamViewFrameBatch(
  datasetId: string,
  viewName: string,
  recordId: string,
  startFrame: number,
  batchSize: number,
  signal?: AbortSignal,
): AsyncGenerator<StreamedFramePart> {
  const params = new URLSearchParams({
    view_name: viewName,
    start_frame: String(startFrame),
    batch_size: String(batchSize),
  });
  const response = await fetch(
    `/datasets/${datasetId}/records/${recordId}/sframes/batch?${params.toString()}`,
    {
      signal,
    },
  );
  if (!response.ok) {
    console.error(
      "api.streamViewFrameBatch -",
      response.status,
      response.statusText,
      await response.text(),
    );
    return;
  }
  if (!response.body) return;

  const boundary = parseBoundary(response.headers.get("content-type"));
  const boundaryBytes = textEncoder.encode(`--${boundary}`);
  const headerSeparatorBytes = textEncoder.encode(HEADER_SEPARATOR);
  const reader = response.body.getReader();

  let buffer: AnyBytes = new Uint8Array(0);
  let done = false;

  while (!done) {
    const read = await reader.read();
    done = read.done;
    if (read.value?.length) {
      buffer = concatBytes(buffer, read.value);
    }

    while (true) {
      const boundaryPos = indexOfBytes(buffer, boundaryBytes);
      if (boundaryPos === -1) {
        // Keep only a small tail to preserve partial boundary splits across chunks.
        const keep = Math.max(boundaryBytes.length * 2, 128);
        if (buffer.length > keep) {
          buffer = buffer.slice(buffer.length - keep);
        }
        break;
      }

      if (boundaryPos > 0) {
        buffer = buffer.slice(boundaryPos);
      }

      if (buffer.length < boundaryBytes.length + 2) break;

      let cursor = boundaryBytes.length;

      // Final boundary marker: `--boundary--`.
      if (buffer[cursor] === DASH && buffer[cursor + 1] === DASH) {
        return;
      }

      // Normal part starts with CRLF after boundary line.
      if (buffer[cursor] === CR && buffer[cursor + 1] === LF) {
        cursor += 2;
      }

      const headersEnd = indexOfBytes(buffer, headerSeparatorBytes, cursor);
      if (headersEnd === -1) break;

      const headers = parseHeaders(textDecoder.decode(buffer.slice(cursor, headersEnd)));
      const contentLength = Number.parseInt(headers.get("content-length") || "0", 10);
      const frameIndex = Number.parseInt(headers.get("x-frame-index") || "-1", 10);
      const contentType = headers.get("content-type") || "application/octet-stream";
      const bodyStart = headersEnd + headerSeparatorBytes.length;
      const bodyEnd = bodyStart + contentLength;

      if (!Number.isFinite(contentLength) || contentLength < 0) {
        // Malformed part; skip the current boundary marker and continue parsing.
        buffer = buffer.slice(boundaryBytes.length);
        continue;
      }

      // Need body bytes + trailing CRLF.
      if (buffer.length < bodyEnd + 2) break;

      if (contentLength > 0 && frameIndex >= 0) {
        yield {
          frameIndex,
          contentType,
          blob: new Blob([buffer.slice(bodyStart, bodyEnd)], { type: contentType }),
        };
      }

      buffer = buffer.slice(bodyEnd + 2);
    }
  }
}

// ─── getViewFrameBatch ──────────────────────────────────────────────────────────

/**
 * Fetch a batch of video frames from the backend batch endpoint.
 *
 * Returns a Map from frame_index to Blob (with correct MIME type).
 */
export async function getViewFrameBatch(
  datasetId: string,
  viewName: string,
  recordId: string,
  startFrame: number,
  batchSize: number,
): Promise<Map<number, Blob>> {
  const frames = new Map<number, Blob>();
  try {
    for await (const part of streamViewFrameBatch(
      datasetId,
      viewName,
      recordId,
      startFrame,
      batchSize,
    )) {
      frames.set(part.frameIndex, part.blob);
    }
    return frames;
  } catch (e) {
    const aborted = e instanceof DOMException && e.name === "AbortError";
    if (!aborted) {
      console.error("api.getViewFrameBatch -", e);
    }
    return frames;
  }
}
