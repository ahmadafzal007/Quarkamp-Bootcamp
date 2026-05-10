import { useState, useRef } from 'react'
import { X, Copy, Download, Check, FileText, RotateCcw } from 'lucide-react'

export default function AssignmentCanvas({ content, skill, score, onClose }) {
  const [text, setText]       = useState(content || '')
  const [copied, setCopied]   = useState(false)
  const textareaRef           = useRef(null)

  const wordCount = text.trim() ? text.trim().split(/\s+/).length : 0
  const charCount = text.length

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {}
  }

  const handleDownload = () => {
    const blob = new Blob([text], { type: 'text/plain' })
    const url  = URL.createObjectURL(blob)
    const a    = document.createElement('a')
    a.href     = url
    a.download = `assignment-${skill || 'output'}-${Date.now()}.txt`
    a.click()
    URL.revokeObjectURL(url)
  }

  const handleReset = () => {
    setText(content || '')
  }

  return (
    <div className="canvas-overlay" onClick={onClose}>
      <div className="canvas-modal" onClick={e => e.stopPropagation()}>

        {/* Header */}
        <div className="canvas-header">
          <div className="canvas-header-left">
            <FileText size={18} className="canvas-header-icon" />
            <div>
              <h2 className="canvas-title">Assignment Canvas</h2>
              <span className="canvas-meta">
                {skill && <span className="canvas-skill">/{skill}</span>}
                {score != null && (
                  <span className={`canvas-score ${score >= 7 ? 'score-good' : 'score-warn'}`}>
                    {score}/10
                  </span>
                )}
              </span>
            </div>
          </div>
          <div className="canvas-header-right">
            <button className="canvas-btn" onClick={handleReset} title="Reset to original">
              <RotateCcw size={15} />
            </button>
            <button className="canvas-btn" onClick={handleCopy} title="Copy to clipboard">
              {copied ? <Check size={15} style={{ color: 'var(--green)' }} /> : <Copy size={15} />}
            </button>
            <button className="canvas-btn" onClick={handleDownload} title="Download as .txt">
              <Download size={15} />
            </button>
            <button className="canvas-btn canvas-btn-close" onClick={onClose}>
              <X size={16} />
            </button>
          </div>
        </div>

        {/* Toolbar row */}
        <div className="canvas-toolbar">
          <span className="canvas-stat">{wordCount} words</span>
          <span className="canvas-stat">{charCount} chars</span>
          <span className="canvas-tip">Click anywhere in the text to edit</span>
        </div>

        {/* Editable content */}
        <div className="canvas-body">
          <textarea
            ref={textareaRef}
            className="canvas-textarea"
            value={text}
            onChange={e => setText(e.target.value)}
            spellCheck={false}
            placeholder="Assignment content will appear here…"
          />
        </div>

      </div>
    </div>
  )
}
