import "./furniture.css";

/**
 * PageHeader — standard header for every routed screen.
 * Eyebrow = where you are (matches the nav label), title = the screen,
 * description = one plain-language sentence saying what the screen does.
 * `actions` renders on the right: status chips, counts, primary CTA.
 */
interface PageHeaderProps {
  eyebrow: string;
  title: string;
  description: string;
  actions?: React.ReactNode;
}

export function PageHeader({ eyebrow, title, description, actions }: PageHeaderProps) {
  return (
    <header className="page-head">
      <div className="ph-main">
        <div className="ph-eyebrow">{eyebrow}</div>
        <h1 className="page-title">{title}</h1>
        <p className="ph-desc">{description}</p>
      </div>
      {actions && <div className="ph-actions">{actions}</div>}
    </header>
  );
}
