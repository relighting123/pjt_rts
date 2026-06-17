import { NAV_ITEMS, type PageId } from "../navigation";

interface Props {
  active: PageId;
  onSelect: (id: PageId) => void;
}

export default function Sidebar({ active, onSelect }: Props) {
  let lastSection = "";

  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <span className="sidebar-logo">RTS</span>
        <span className="sidebar-title">ML 파이프라인</span>
      </div>
      <nav className="sidebar-nav">
        {NAV_ITEMS.map((item) => {
          const showSection = item.section && item.section !== lastSection;
          if (showSection) lastSection = item.section!;
          return (
            <span key={item.id}>
              {showSection && <div className="sidebar-section">{item.section}</div>}
              <button
                type="button"
                className={`sidebar-link${active === item.id ? " active" : ""}`}
                onClick={() => onSelect(item.id)}
              >
                {item.label}
              </button>
            </span>
          );
        })}
      </nav>
    </aside>
  );
}
