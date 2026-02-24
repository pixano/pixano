/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

const BOUNDARY = "frame_boundary";

/**
 * Parse a multipart/x-mixed-replace response body into a Map of frame_index → Blob.
 */
function parseMultipartFrames(buffer: ArrayBuffer): Map<number, Blob> {
  const frames = new Map<number, Blob>();
  const bytes = new Uint8Array(buffer);
  const decoder = new TextDecoder();

  const boundaryMarker = `--${BOUNDARY}`;
  const endMarker = `--${BOUNDARY}--`;
  const headerBodySep = "\r\n\r\n";

  // Convert to string to find boundary positions, but only for headers.
  // We'll work byte-level for the binary body extraction.
  let offset = 0;

  while (offset < bytes.length) {
    // Find next boundary
    const remaining = decoder.decode(bytes.subarray(offset, Math.min(offset + 200, bytes.length)));
    const boundaryPos = remaining.indexOf(boundaryMarker);
    if (boundaryPos === -1) break;

    // Check for end boundary
    if (remaining.indexOf(endMarker) === boundaryPos) break;

    // Move past the boundary line
    const afterBoundary = offset + boundaryPos + boundaryMarker.length;
    // Skip \r\n after boundary marker
    const afterBoundaryBytes = bytes.subarray(afterBoundary);
    let headerStart = afterBoundary;
    if (afterBoundaryBytes[0] === 0x0d && afterBoundaryBytes[1] === 0x0a) {
      headerStart = afterBoundary + 2;
    }

    // Find the header/body separator (\r\n\r\n)
    let sepPos = -1;
    for (let i = headerStart; i < bytes.length - 3; i++) {
      if (
        bytes[i] === 0x0d &&
        bytes[i + 1] === 0x0a &&
        bytes[i + 2] === 0x0d &&
        bytes[i + 3] === 0x0a
      ) {
        sepPos = i;
        break;
      }
    }
    if (sepPos === -1) break;

    // Parse headers
    const headersStr = decoder.decode(bytes.subarray(headerStart, sepPos));
    const headers = new Map<string, string>();
    for (const line of headersStr.split("\r\n")) {
      const colonIdx = line.indexOf(":");
      if (colonIdx !== -1) {
        headers.set(line.substring(0, colonIdx).trim().toLowerCase(), line.substring(colonIdx + 1).trim());
      }
    }

    const bodyStart = sepPos + headerBodySep.length;
    const contentLength = parseInt(headers.get("content-length") || "0", 10);
    const contentType = headers.get("content-type") || "application/octet-stream";
    const frameIndex = parseInt(headers.get("x-frame-index") || "-1", 10);

    if (contentLength > 0 && frameIndex >= 0) {
      const bodyEnd = bodyStart + contentLength;
      const bodySlice = bytes.slice(bodyStart, bodyEnd);
      frames.set(frameIndex, new Blob([bodySlice], { type: contentType }));
      // Move past body + trailing \r\n
      offset = bodyEnd + 2;
    } else {
      // Skip malformed part
      offset = bodyStart + Math.max(contentLength, 0) + 2;
    }
  }

  return frames;
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
  itemId: string,
  startFrame: number,
  batchSize: number,
): Promise<Map<number, Blob>> {
  try {
    const params = new URLSearchParams({
      item_id: itemId,
      start_frame: String(startFrame),
      batch_size: String(batchSize),
    });
    const response = await fetch(
      `/views/${datasetId}/${viewName}/batch?${params.toString()}`,
    );
    if (!response.ok) {
      console.error(
        "api.getViewFrameBatch -",
        response.status,
        response.statusText,
        await response.text(),
      );
      return new Map();
    }
    const buffer = await response.arrayBuffer();
    return parseMultipartFrames(buffer);
  } catch (e) {
    console.error("api.getViewFrameBatch -", e);
    return new Map();
  }
}
