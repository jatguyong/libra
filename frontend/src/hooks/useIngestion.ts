/**
 * useIngestion — custom hook for PDF ingestion state management.
 *
 * Encapsulates:
 *   - File list and status tracking
 *   - Background polling while files are processing
 *   - Upload callback and remove/cancel handler
 */

import { useState, useEffect, useCallback } from 'react';
import { API_BASE } from '../lib/api';

interface FileStatus {
  status: string;
  duration_s?: number;
  error?: string;
}

export interface IngestionState {
  uploadedFiles: File[];
  setUploadedFiles: React.Dispatch<React.SetStateAction<File[]>>;
  fileStatuses: Record<string, FileStatus>;
  hasProcessing: boolean;
  handleFilesUploaded: (files: File[]) => void;
  handleRemoveFile: (filename: string) => void;
  handleClearAll: () => Promise<void>;
  reset: () => void;
}

export function useIngestion(): IngestionState {
  const [uploadedFiles, setUploadedFiles] = useState<File[]>([]);
  const [fileStatuses, setFileStatuses] = useState<Record<string, FileStatus>>({});

  const hasProcessing = Object.values(fileStatuses).some(s => s.status === 'processing');

  // Poll ingestion status while any file is processing
  useEffect(() => {
    if (!hasProcessing) return;

    const interval = setInterval(async () => {
      try {
        const res = await fetch(`${API_BASE}/api/ingest/status`);
        if (res.ok) {
          const data = await res.json();
          setFileStatuses(data);
        }
      } catch (err) {
        console.error('Error polling ingestion status:', err);
      }
    }, 3000);

    return () => clearInterval(interval);
  }, [hasProcessing]);

  const handleFilesUploaded = useCallback((files: File[]) => {
    setUploadedFiles(prev => [...prev, ...files]);
    const newStatuses: Record<string, FileStatus> = {};
    files.forEach(f => { newStatuses[f.name] = { status: 'processing' }; });
    setFileStatuses(prev => ({ ...prev, ...newStatuses }));
  }, []);

  const handleRemoveFile = useCallback(async (filename: string) => {
    // Optimistically remove from UI
    setUploadedFiles(prev => prev.filter(f => f.name !== filename));
    setFileStatuses(prev => {
      const next = { ...prev };
      delete next[filename];
      return next;
    });

    const isProcessing = fileStatuses[filename]?.status === 'processing';
    const endpoint = isProcessing ? '/api/ingest/cancel' : '/api/ingest/remove';
    try {
      await fetch(`${API_BASE}${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ filename }),
      });
    } catch (err) {
      console.error(`Error calling ${endpoint} for ${filename}:`, err);
    }
  }, [fileStatuses]);

  const handleClearAll = useCallback(async () => {
    // Optimistically clear the UI
    setUploadedFiles([]);
    setFileStatuses({});
    try {
      await fetch(`${API_BASE}/api/ingest/clear`, { method: 'POST' });
    } catch (err) {
      console.error('Error clearing all documents:', err);
    }
  }, []);

  const reset = useCallback(() => {
    setUploadedFiles([]);
    setFileStatuses({});
  }, []);

  // Fetch already-ingested documents on initial mount
  useEffect(() => {
    async function fetchIngestedDocs() {
      try {
        const res = await fetch(`${API_BASE}/api/ingest/documents`);
        if (res.ok) {
          const data = await res.json();
          if (data.documents && Array.isArray(data.documents)) {
            // Reconstruct pseudo-File objects just for the filename in the UI
            const recoveredFiles = data.documents.map((doc: { path: string }) => {
              // Create a dummy file object using File constructor
              return new File([], doc.path);
            });
            
            setUploadedFiles(prev => {
              // Avoid duplicates if uploads happened before fetch completes
              const existingNames = new Set(prev.map(f => f.name));
              const newFiles = recoveredFiles.filter((f: File) => !existingNames.has(f.name));
              return [...prev, ...newFiles];
            });

            // Set their statuses to done
            setFileStatuses(prev => {
              const next = { ...prev };
              recoveredFiles.forEach((f: File) => {
                if (!next[f.name]) {
                  next[f.name] = { status: 'done' };
                }
              });
              return next;
            });
          }
        }
      } catch (err) {
        console.error('Error fetching ingested documents:', err);
      }
    }
    fetchIngestedDocs();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return {
    uploadedFiles,
    setUploadedFiles,
    fileStatuses,
    hasProcessing,
    handleFilesUploaded,
    handleRemoveFile,
    handleClearAll,
    reset,
  };
}
