interface AttachmentPreviewProps {
  files: File[];
  disabled?: boolean;
  onFilesAdded: (files: File[]) => void;
  onRemove: (index: number) => void;
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function getFileIcon(fileName: string): string {
  const ext = fileName.split('.').pop()?.toLowerCase() || '';
  if (['pdf'].includes(ext)) return '📄';
  if (['csv', 'xlsx', 'xls'].includes(ext)) return '📊';
  if (['jpg', 'jpeg', 'png', 'gif', 'webp'].includes(ext)) return '🖼️';
  if (['mp4', 'webm', 'mov'].includes(ext)) return '🎬';
  if (['txt', 'md', 'json', 'yaml', 'xml'].includes(ext)) return '📝';
  if (['js', 'ts', 'tsx', 'jsx', 'py', 'java', 'cs', 'go', 'rb', 'php'].includes(ext)) return '💻';
  return '📎';
}

export function AttachmentPreview({
  files,
  disabled = false,
  onFilesAdded,
  onRemove,
}: AttachmentPreviewProps) {
  return (
    <div
      className={`attachment-preview ${disabled ? 'attachment-preview-disabled' : ''}`}
      onDragOver={(event) => {
        if (!disabled) {
          event.preventDefault();
          event.currentTarget.classList.add('attachment-preview-drag');
        }
      }}
      onDragLeave={(event) => {
        event.currentTarget.classList.remove('attachment-preview-drag');
      }}
      onDrop={(event) => {
        event.preventDefault();
        event.currentTarget.classList.remove('attachment-preview-drag');
        if (disabled) return;
        const dropped = Array.from(event.dataTransfer.files ?? []);
        if (dropped.length > 0) {
          onFilesAdded(dropped);
        }
      }}
    >
      {files.length === 0 ? (
        <div className="attachment-preview-empty">
          <div className="attachment-preview-title">Drag files here to attach</div>
          <div className="attachment-preview-subtitle">Support: PDF, images, CSV, code, text (max 20MB each)</div>
        </div>
      ) : (
        <div>
          <div className="attachment-preview-count">
            {files.length} file{files.length !== 1 ? 's' : ''} selected
          </div>
          <div className="attachment-chip-list">
            {files.map((file, index) => (
              <div
                key={`${file.name}:${file.size}:${file.lastModified}`}
                className="attachment-chip"
              >
                <span className="attachment-chip-icon">{getFileIcon(file.name)}</span>
                <div className="attachment-chip-content">
                  <div className="attachment-chip-name" title={file.name}>{file.name}</div>
                  <div className="attachment-chip-size">{formatFileSize(file.size)}</div>
                </div>
                <button
                  type="button"
                  className="attachment-chip-remove"
                  disabled={disabled}
                  onClick={() => onRemove(index)}
                  title="Remove this file"
                >
                  ✕
                </button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
