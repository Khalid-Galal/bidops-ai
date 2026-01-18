import { useState, useRef } from 'react';
import { useParams } from 'react-router-dom';
import {
  DocumentIcon,
  CloudArrowUpIcon,
  FolderPlusIcon,
  TrashIcon,
  ArrowPathIcon,
} from '@heroicons/react/24/outline';
import { Card, CardBody, Button, DataTable, Modal, ModalFooter, Input, StatusBadge } from '@/components/ui';
import { useDocuments, useUploadDocument, useUploadFolder, useDeleteDocument, useReprocessDocument } from '@/hooks/useDocuments';
import type { Document } from '@/types';
import type { Column } from '@/components/ui/DataTable';

function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

export default function DocumentsPage() {
  const { id } = useParams<{ id: string }>();
  const projectId = parseInt(id || '0');
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [isFolderModalOpen, setIsFolderModalOpen] = useState(false);
  const [folderPath, setFolderPath] = useState('');
  const [uploadProgress, setUploadProgress] = useState<number | null>(null);

  const { data, isLoading } = useDocuments(projectId);
  const uploadDocument = useUploadDocument(projectId);
  const uploadFolder = useUploadFolder(projectId);
  const deleteDocument = useDeleteDocument(projectId);
  const reprocessDocument = useReprocessDocument(projectId);

  const columns: Column<Document>[] = [
    {
      key: 'filename',
      header: 'Document',
      render: (doc) => (
        <div className="flex items-center gap-3">
          <DocumentIcon className="w-8 h-8 text-gray-400" />
          <div>
            <p className="font-medium text-gray-900">{doc.filename}</p>
            <p className="text-sm text-gray-500">
              {doc.category || 'Uncategorized'} - {formatFileSize(doc.file_size)}
            </p>
          </div>
        </div>
      ),
    },
    {
      key: 'status',
      header: 'Status',
      render: (doc) => <StatusBadge status={doc.status} />,
    },
    {
      key: 'page_count',
      header: 'Pages',
      render: (doc) => doc.page_count || '-',
    },
    {
      key: 'created_at',
      header: 'Uploaded',
      render: (doc) => new Date(doc.created_at).toLocaleDateString(),
    },
    {
      key: 'actions',
      header: '',
      render: (doc) => (
        <div className="flex justify-end gap-2">
          <button
            onClick={(e) => {
              e.stopPropagation();
              reprocessDocument.mutate(doc.id);
            }}
            className="p-1 text-gray-400 hover:text-primary-600"
            title="Reprocess"
          >
            <ArrowPathIcon className="w-5 h-5" />
          </button>
          <button
            onClick={(e) => {
              e.stopPropagation();
              if (confirm('Delete this document?')) {
                deleteDocument.mutate(doc.id);
              }
            }}
            className="p-1 text-gray-400 hover:text-red-600"
            title="Delete"
          >
            <TrashIcon className="w-5 h-5" />
          </button>
        </div>
      ),
    },
  ];

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;

    for (const file of Array.from(files)) {
      await uploadDocument.mutateAsync({
        file,
        onProgress: setUploadProgress,
      });
    }
    setUploadProgress(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const handleFolderUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    await uploadFolder.mutateAsync(folderPath);
    setIsFolderModalOpen(false);
    setFolderPath('');
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Documents</h1>
          <p className="mt-1 text-gray-500">Upload and manage tender documents</p>
        </div>
        <div className="flex gap-3">
          <Button variant="outline" onClick={() => setIsFolderModalOpen(true)}>
            <FolderPlusIcon className="w-5 h-5 mr-2" />
            Upload Folder
          </Button>
          <Button onClick={() => fileInputRef.current?.click()}>
            <CloudArrowUpIcon className="w-5 h-5 mr-2" />
            Upload Files
          </Button>
          <input
            ref={fileInputRef}
            type="file"
            multiple
            onChange={handleFileUpload}
            className="hidden"
            accept=".pdf,.doc,.docx,.xls,.xlsx,.dwg,.dxf"
          />
        </div>
      </div>

      {/* Upload Progress */}
      {uploadProgress !== null && (
        <div className="bg-primary-50 rounded-lg p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-medium text-primary-700">Uploading...</span>
            <span className="text-sm text-primary-600">{uploadProgress}%</span>
          </div>
          <div className="w-full bg-primary-200 rounded-full h-2">
            <div
              className="bg-primary-600 h-2 rounded-full transition-all duration-300"
              style={{ width: `${uploadProgress}%` }}
            />
          </div>
        </div>
      )}

      {/* Documents Table */}
      <Card>
        <CardBody className="p-0">
          <DataTable
            columns={columns}
            data={data?.items || []}
            keyExtractor={(doc) => doc.id}
            isLoading={isLoading}
            emptyMessage="No documents uploaded yet. Upload files to get started."
          />
        </CardBody>
      </Card>

      {/* Pagination Info */}
      {data && data.total > 0 && (
        <div className="text-sm text-gray-500">
          Showing {data.items.length} of {data.total} documents
        </div>
      )}

      {/* Folder Upload Modal */}
      <Modal
        isOpen={isFolderModalOpen}
        onClose={() => setIsFolderModalOpen(false)}
        title="Upload Folder"
        description="Enter the path to the folder containing tender documents"
      >
        <form onSubmit={handleFolderUpload} className="space-y-4">
          <Input
            label="Folder Path"
            value={folderPath}
            onChange={(e) => setFolderPath(e.target.value)}
            placeholder="e.g., C:\Tenders\Project-123"
            required
          />
          <p className="text-sm text-gray-500">
            The folder will be scanned for PDF, Word, Excel, and CAD files.
          </p>
          <ModalFooter className="-mx-6 -mb-4 mt-6">
            <Button variant="outline" type="button" onClick={() => setIsFolderModalOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" isLoading={uploadFolder.isPending}>
              Upload Folder
            </Button>
          </ModalFooter>
        </form>
      </Modal>
    </div>
  );
}
