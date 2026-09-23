/*-------------------------------------
Copyright: CEA-LIST/DIASI/SIALV/LVA
Author : pixano@cea.fr
License: CECILL-C
-------------------------------------*/

/** Client-side folder upload: the wizard stages the user's local folder on the server. */

import { createUploadSession, deleteUploadSession } from "./ioApi";

/** One file of a picked folder, keyed by its path inside that folder. */
export interface UploadEntry {
  relPath: string;
  file: File;
}

export interface FolderSelection {
  folderName: string;
  entries: UploadEntry[];
  totalBytes: number;
}

export interface UploadProgress {
  uploadedBytes: number;
  totalBytes: number;
  uploadedFiles: number;
  totalFiles: number;
}

/**
 * Turn a `webkitdirectory` FileList into upload entries.
 *
 * Browsers prefix every `webkitRelativePath` with the picked folder's name;
 * that shared first segment is stripped from the staged paths and returned
 * as `folderName` (the wizard's default dataset name).
 */
export function splitFolderSelection(files: readonly File[]): FolderSelection {
  const entries: UploadEntry[] = [];
  let folderName = "";
  let totalBytes = 0;
  for (const file of files) {
    const relative = file.webkitRelativePath || file.name;
    const separator = relative.indexOf("/");
    const root = separator === -1 ? "" : relative.slice(0, separator);
    const relPath = separator === -1 ? relative : relative.slice(separator + 1);
    if (!relPath || relPath.endsWith("/")) continue;
    folderName = folderName || root;
    entries.push({ relPath, file });
    totalBytes += file.size;
  }
  return { folderName, entries, totalBytes };
}

/**
 * Keep only the entries whose file name passes `keep`.
 *
 * Raw-media imports upload just the media matching the chosen kind, so stray
 * files (a leftover `metadata.jsonl`, `.DS_Store`, a README) never reach the
 * server — where a `metadata.jsonl` would silently disable media-only mode.
 */
export function filterSelection(
  selection: FolderSelection,
  keep: (name: string) => boolean,
): FolderSelection {
  const entries = selection.entries.filter((entry) => keep(entry.file.name));
  return {
    folderName: selection.folderName,
    entries,
    totalBytes: entries.reduce((sum, entry) => sum + entry.file.size, 0),
  };
}

const UPLOAD_CONCURRENCY = 3;

/** PUT one file's raw body with byte-accurate progress (XHR: fetch cannot report upload progress). */
function putFile(
  uploadId: string,
  entry: UploadEntry,
  onBytes: (bytes: number) => void,
  signal: AbortSignal,
): Promise<void> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    const encoded = entry.relPath.split("/").map(encodeURIComponent).join("/");
    xhr.open("PUT", `/io/uploads/${uploadId}/files/${encoded}`);
    let sent = 0;
    xhr.upload.onprogress = (event) => {
      onBytes(event.loaded - sent);
      sent = event.loaded;
    };
    xhr.onload = () => {
      onBytes(entry.file.size - sent);
      sent = entry.file.size;
      if (xhr.status >= 200 && xhr.status < 300) resolve();
      else reject(new Error(`Upload of '${entry.relPath}' failed (${xhr.status}).`));
    };
    xhr.onerror = () => reject(new Error(`Upload of '${entry.relPath}' failed.`));
    xhr.onabort = () => reject(new DOMException("Upload cancelled.", "AbortError"));
    signal.addEventListener("abort", () => xhr.abort(), { once: true });
    xhr.send(entry.file);
  });
}

/**
 * Upload a picked folder into a fresh staging session.
 *
 * Returns the staged server path to use as the import `source`. On failure or
 * abort the session is discarded server-side before rethrowing.
 */
export async function uploadFolder(
  selection: FolderSelection,
  onProgress: (progress: UploadProgress) => void,
  signal: AbortSignal,
): Promise<{ source: string; uploadId: string }> {
  if (!selection.entries.length) throw new Error("The selected folder contains no files.");
  const session = await createUploadSession();
  const progress: UploadProgress = {
    uploadedBytes: 0,
    totalBytes: selection.totalBytes,
    uploadedFiles: 0,
    totalFiles: selection.entries.length,
  };
  const queue = [...selection.entries];

  async function worker(): Promise<void> {
    for (let entry = queue.shift(); entry !== undefined; entry = queue.shift()) {
      if (signal.aborted) throw new DOMException("Upload cancelled.", "AbortError");
      await putFile(
        session.upload_id,
        entry,
        (bytes) => {
          progress.uploadedBytes += bytes;
          onProgress({ ...progress });
        },
        signal,
      );
      progress.uploadedFiles += 1;
      onProgress({ ...progress });
    }
  }

  try {
    await Promise.all(
      Array.from({ length: Math.min(UPLOAD_CONCURRENCY, queue.length) }, () => worker()),
    );
  } catch (error) {
    void deleteUploadSession(session.upload_id).catch(() => undefined);
    throw error;
  }
  return { source: session.source, uploadId: session.upload_id };
}
