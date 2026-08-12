const TERMINAL_STATUSES = new Set(['indexed', 'failed', 'deleted']);

const wait = (milliseconds) => new Promise(resolve => window.setTimeout(resolve, milliseconds));

export async function pollDocumentStatus({
  apiUrl,
  accessToken,
  documentId,
  onStatus,
  maxAttempts = 120,
  intervalMs = 1500,
  signal,
}) {
  for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
    if (signal?.aborted) throw new DOMException('Polling was cancelled.', 'AbortError');
    const response = await fetch(`${apiUrl}/api/documents/${encodeURIComponent(documentId)}/status`, {
      headers: { Authorization: `Bearer ${accessToken}` },
      signal,
    });
    let data = {};
    try { data = await response.json(); } catch {}
    if (!response.ok) throw new Error(data.detail || 'Document status is unavailable.');
    const document = data.document || data;
    const job = data.job || null;
    onStatus?.({ document, job });
    if (TERMINAL_STATUSES.has(document.status)) return { document, job };
    await wait(intervalMs);
  }
  throw new Error('Document processing is taking longer than expected. Check the inventory again shortly.');
}

export function documentHistoryEntry(document, fallback = {}) {
  const status = document?.status || fallback.status || 'processing';
  return {
    id: document?.id || fallback.id,
    name: document?.file_name || fallback.name || 'Document.pdf',
    size: document?.byte_size ? `${(document.byte_size / 1024).toFixed(1)} KB` : fallback.size || 'Size unavailable',
    date: document?.created_at
      ? new Date(document.created_at).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })
      : fallback.date || 'Date unavailable',
    status: status === 'indexed' ? 'success' : status === 'failed' ? 'error' : 'processing',
    progress: Number.isFinite(document?.processing_progress) ? document.processing_progress : (fallback.progress || 0),
    stage: document?.processing_stage || fallback.stage || (status === 'indexed' ? 'complete' : 'queued'),
    message: document?.error_message || fallback.message || (status === 'indexed' ? 'Indexed for document-grounded answers.' : 'Queued for processing.'),
  };
}
