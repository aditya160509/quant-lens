import type { CSSProperties, MouseEventHandler, ReactNode, Ref } from "react";

/** One numbered output: a finding as the title when there is one, the name otherwise, then tools and body. */
export function Exhibit({ id, name, finding, hint, note, tools, className = "card", wide, flush, level = 3, style, bodyRef, onContextMenu, after, children }: {
  id: string;
  name: ReactNode;
  finding?: ReactNode;
  hint?: ReactNode;
  note?: ReactNode;
  tools?: ReactNode;
  className?: string;
  wide?: boolean;
  flush?: boolean;
  level?: 2 | 3;
  style?: CSSProperties;
  bodyRef?: Ref<HTMLDivElement>;
  onContextMenu?: MouseEventHandler<HTMLElement>;
  after?: ReactNode;
  children: ReactNode;
}) {
  const Heading = `h${level}` as const;
  return (
    <section className={className} id={`out-${id}`} aria-labelledby={`h-${id}`} data-wide={wide || undefined} style={style} onContextMenu={onContextMenu}>
      <header className="card-h">
        <div style={{ minWidth: 0, display: "grid", gap: finding ? 3 : undefined }}>
          {finding ? <span className="ex-no">{name}</span> : null}
          <Heading id={`h-${id}`} className={finding ? "ex-title" : undefined}>{finding ?? name}</Heading>
          {!finding && hint ? <span className="sub">{hint}</span> : null}
        </div>
        {tools ? <div className="tools">{tools}</div> : null}
      </header>
      <div ref={bodyRef} className={`card-b${flush ? " flush" : ""}`}>{children}</div>
      {note ? <p className="card-note">{note}</p> : null}
      {after}
    </section>
  );
}
