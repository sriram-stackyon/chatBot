import { Attachment } from '../../types/chat';

interface MessageAttachmentsProps {
  attachments: Attachment[];
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function MessageAttachments({ attachments }: MessageAttachmentsProps) {
  return (
    <div className="message-attachments">
      {attachments.map((attachment) => {
        const imageUrl = attachment.publicUrl ?? attachment.imageUrl ?? null;
        const isImage = (attachment.attachmentType === 'image' || attachment.attachmentType === 'generated_image') && imageUrl;
        return (
          <div key={attachment.id} className="message-attachment-card">
            {isImage && (
              <img
                src={imageUrl ?? undefined}
                alt={attachment.originalFilename}
                className="message-attachment-image"
              />
            )}
            <div className="message-attachment-title">{attachment.originalFilename}</div>
            <div className="message-attachment-meta">
              {attachment.attachmentType} · {attachment.mimeType} · {formatFileSize(attachment.fileSize)}
            </div>

            {attachment.promptUsed && (
              <div className="message-attachment-prompt">Prompt: {attachment.promptUsed}</div>
            )}

            <div className="message-attachment-actions">
              <a
                href={imageUrl ?? attachment.publicUrl ?? '#'}
                target="_blank"
                rel="noreferrer"
                className="message-attachment-link"
              >
                Open
              </a>
              <a
                href={imageUrl ?? attachment.publicUrl ?? '#'}
                download={attachment.originalFilename}
                className="message-attachment-link"
              >
                Download
              </a>
            </div>
          </div>
        );
      })}
    </div>
  );
}
