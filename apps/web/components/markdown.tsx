"use client";

import ReactMarkdown from "react-markdown";
import rehypeSanitize from "rehype-sanitize";
import remarkGfm from "remark-gfm";

interface MarkdownProps {
  content: string;
}

/**
 * Safe Markdown renderer for assistant replies.
 *
 * - GFM (tables, task lists, strikethrough) via remark-gfm.
 * - Raw HTML is stripped by rehype-sanitize (XSS protection).
 * - External links open in a new tab with noopener/noreferrer.
 */
export function Markdown({ content }: MarkdownProps) {
  return (
    <div className="markdown-body">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[rehypeSanitize]}
        components={{
          a: ({ children, ...props }) => (
            <a
              {...props}
              target="_blank"
              rel="noopener noreferrer"
              className="text-blue-600 underline hover:text-blue-700"
            >
              {children}
            </a>
          ),
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
