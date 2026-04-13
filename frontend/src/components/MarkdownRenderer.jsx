import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { Copy, Check } from 'lucide-react';

const CodeBlock = ({ language, children }) => {
  const [copied, setCopied] = React.useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(children);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div style={{ position: 'relative', group: 'code-block' }}>
      <button
        onClick={handleCopy}
        style={{
          position: 'absolute',
          top: '0.75rem',
          right: '0.75rem',
          padding: '0.4rem',
          backgroundColor: 'rgba(255, 255, 255, 0.05)',
          border: '1px solid rgba(255, 255, 255, 0.1)',
          borderRadius: '0.5rem',
          color: copied ? 'var(--accent-color)' : 'var(--text-secondary)',
          cursor: 'pointer',
          zIndex: 10,
          display: 'flex',
          alignItems: 'center',
          gap: '0.4rem',
          fontSize: '0.75rem',
          transition: 'all 0.2s ease',
          backdropFilter: 'blur(4px)',
        }}
        title="Copy code"
      >
        {copied ? <Check size={14} /> : <Copy size={14} />}
        {copied ? 'Copied!' : 'Copy'}
      </button>
      <SyntaxHighlighter
        style={vscDarkPlus}
        language={language}
        PreTag="div"
        customStyle={{
          margin: '1rem 0',
          borderRadius: '0.75rem',
          fontSize: '0.9rem',
          backgroundColor: 'rgba(0, 0, 0, 0.4)',
          border: '1px solid rgba(255, 255, 255, 0.1)',
          padding: '1.25rem',
        }}
      >
        {children}
      </SyntaxHighlighter>
    </div>
  );
};

const MarkdownRenderer = ({ content }) => {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        code({ node, inline, className, children, ...props }) {
          const match = /language-(\w+)/.exec(className || '');
          const codeString = String(children).replace(/\n$/, '');
          
          return !inline && match ? (
            <CodeBlock language={match[1]}>
              {codeString}
            </CodeBlock>
          ) : (
            <code 
              className={className} 
              style={{
                backgroundColor: 'rgba(255, 255, 255, 0.1)',
                padding: '0.2rem 0.4rem',
                borderRadius: '0.3rem',
                fontSize: '0.85em',
                fontFamily: 'monospace',
                color: 'var(--accent-color)'
              }}
              {...props}
            >
              {children}
            </code>
          );
        },
        p: ({ children }) => <p style={{ marginBottom: '1rem', lineHeight: '1.7' }}>{children}</p>,
        ul: ({ children }) => <ul style={{ marginLeft: '1.5rem', marginBottom: '1rem', listStyleType: 'disc' }}>{children}</ul>,
        ol: ({ children }) => <ol style={{ marginLeft: '1.5rem', marginBottom: '1rem', listStyleType: 'decimal' }}>{children}</ol>,
        li: ({ children }) => <li style={{ marginBottom: '0.5rem' }}>{children}</li>,
        h1: ({ children }) => <h1 style={{ fontSize: '1.5rem', fontWeight: '700', margin: '1.5rem 0 1rem' }}>{children}</h1>,
        h2: ({ children }) => <h2 style={{ fontSize: '1.35rem', fontWeight: '600', margin: '1.25rem 0 0.75rem' }}>{children}</h2>,
        h3: ({ children }) => <h3 style={{ fontSize: '1.2rem', fontWeight: '600', margin: '1rem 0 0.5rem' }}>{children}</h3>,
        table: ({ children }) => (
          <div style={{ overflowX: 'auto', marginBottom: '1rem' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', border: '1px solid var(--border-color)' }}>{children}</table>
          </div>
        ),
        thead: ({ children }) => <thead style={{ backgroundColor: 'var(--bg-surface)' }}>{children}</thead>,
        th: ({ children }) => <th style={{ padding: '0.75rem', border: '1px solid var(--border-color)', textAlign: 'left', fontWeight: '600' }}>{children}</th>,
        td: ({ children }) => <td style={{ padding: '0.75rem', border: '1px solid var(--border-color)' }}>{children}</td>,
        blockquote: ({ children }) => (
          <blockquote style={{ borderLeft: '4px solid var(--accent-color)', paddingLeft: '1rem', color: 'var(--text-secondary)', fontStyle: 'italic', margin: '1rem 0' }}>
            {children}
          </blockquote>
        ),
        a: ({ href, children }) => (
          <a href={href} target="_blank" rel="noopener noreferrer" style={{ color: 'var(--accent-color)', textDecoration: 'underline' }}>
            {children}
          </a>
        )
      }}
    >
      {content}
    </ReactMarkdown>
  );
};

export default MarkdownRenderer;
