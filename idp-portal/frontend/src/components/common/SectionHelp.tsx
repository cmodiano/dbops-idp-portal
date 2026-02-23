import { useState } from 'react';
import { Tooltip, Popover, Spin } from 'antd';
import { QuestionCircleOutlined } from '@ant-design/icons';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeSanitize from 'rehype-sanitize';
import { useHelpContent } from '../../hooks/useHelpContent';

export interface SectionHelpProps {
  topicId: string;
  mode?: 'tooltip' | 'popover' | 'both';
}

export default function SectionHelp({
  topicId,
  mode = 'both',
}: SectionHelpProps) {
  const { content, loading } = useHelpContent(topicId);
  const [popoverOpen, setPopoverOpen] = useState(false);

  if (loading) {
    return (
      <Spin size="small" style={{ marginLeft: 4 }} />
    );
  }

  const showTooltip = mode === 'tooltip' || mode === 'both';
  const showPopover = mode === 'popover' || mode === 'both';

  const markdownContent = (
    <div style={{ maxWidth: 400, maxHeight: 400, overflowY: 'auto' }}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeSanitize]}
      >
        {content?.markdown || ''}
      </ReactMarkdown>
    </div>
  );

  const icon = (
    <QuestionCircleOutlined
      role="button"
      aria-label="Aide pour cette section"
      tabIndex={0}
      style={{ marginLeft: 4, color: '#1677ff', cursor: 'pointer' }}
      onClick={showPopover ? () => setPopoverOpen(!popoverOpen) : undefined}
    />
  );

  if (showPopover && showTooltip) {
    return (
      <Popover
        content={markdownContent}
        title={content?.short || undefined}
        trigger="click"
        open={popoverOpen}
        onOpenChange={setPopoverOpen}
      >
        <Tooltip title={content?.short || undefined}>
          {icon}
        </Tooltip>
      </Popover>
    );
  }

  if (showPopover) {
    return (
      <Popover
        content={markdownContent}
        title={content?.short || undefined}
        trigger="click"
        open={popoverOpen}
        onOpenChange={setPopoverOpen}
      >
        {icon}
      </Popover>
    );
  }

  // tooltip only
  return (
    <Tooltip title={content?.short || undefined}>
      {icon}
    </Tooltip>
  );
}
