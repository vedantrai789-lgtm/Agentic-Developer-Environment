import { useEffect, useRef } from 'react';
import hljs from 'highlight.js/lib/core';
import diff from 'highlight.js/lib/languages/diff';
import 'highlight.js/styles/github-dark.css';

hljs.registerLanguage('diff', diff);

interface Props {
  filePath: string;
  changeType: string;
  content: string | null;
}

const typeColors: Record<string, string> = {
  create: 'text-green-400',
  modify: 'text-amber-400',
  delete: 'text-red-400',
};

export function DiffViewer({ filePath, changeType, content }: Props) {
  const codeRef = useRef<HTMLElement>(null);

  useEffect(() => {
    if (codeRef.current && content) {
      codeRef.current.textContent = content;
      hljs.highlightElement(codeRef.current);
    }
  }, [content]);

  return (
    <div className="overflow-hidden rounded border border-slate-700 bg-slate-950">
      <div className="flex items-center gap-2 border-b border-slate-700 bg-slate-800 px-3 py-1.5 text-xs">
        <span className={typeColors[changeType] || 'text-slate-400'}>{changeType}</span>
        <span className="font-mono text-slate-300">{filePath}</span>
      </div>
      {content ? (
        <pre className="overflow-x-auto p-3 text-xs">
          <code ref={codeRef} className="language-diff">
            {content}
          </code>
        </pre>
      ) : (
        <p className="px-3 py-2 text-xs text-slate-500">No diff available</p>
      )}
    </div>
  );
}
