import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

/**
 * Renders Markdown with GFM (tables, strikethrough, task lists, autolinks).
 * Safe: no raw HTML — only parsed markdown AST.
 */
export default function MarkdownBody({ children, className = '' }) {
  const text = typeof children === 'string' ? children : String(children ?? '')

  return (
    <div className={`md-body ${className}`.trim()}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          a({ node: _n, ...props }) {
            return <a target="_blank" rel="noopener noreferrer" {...props} />
          },
        }}
      >
        {text}
      </ReactMarkdown>
    </div>
  )
}
