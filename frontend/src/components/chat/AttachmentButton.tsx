interface AttachmentButtonProps {
  disabled?: boolean;
  onFilesSelected: (files: File[]) => void;
}

export function AttachmentButton({ disabled = false, onFilesSelected }: AttachmentButtonProps) {
  return (
    <label
      className={`attachment-button ${disabled ? 'attachment-button-disabled' : ''}`}
      title="Attach files (images, PDFs, CSV, text, code)"
    >
      <input
        type="file"
        multiple
        className="attachment-input-hidden"
        disabled={disabled}
        accept=".pdf,.csv,.xlsx,.xls,.txt,.md,.json,.yaml,.xml,.js,.ts,.tsx,.jsx,.py,.java,.cs,.go,.rb,.php,.jpg,.jpeg,.png,.gif,.webp,.mp4,.webm,.mov"
        onChange={(event) => {
          const files = Array.from(event.target.files ?? []);
          if (files.length > 0) {
            onFilesSelected(files);
          }
          event.currentTarget.value = '';
        }}
      />
      <svg className="attachment-button-icon" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
      </svg>
      <span>Attach</span>
    </label>
  );
}
