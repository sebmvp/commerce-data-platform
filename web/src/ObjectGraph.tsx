import type { ContextBundle, ContextObject } from "./types";
import { itemLabel, objectLabel, parseRef, relVerb, typeLabel } from "./format";

export function ObjectGraph({
  bundle,
  onOpen,
}: {
  bundle: ContextBundle;
  onOpen: (obj: ContextObject) => void;
}) {
  const rels = bundle.relationships || [];
  const objects = bundle.objects || [];
  if (!rels.length && !objects.length) {
    return <p className="empty">No related objects assembled.</p>;
  }

  const children = new Map<string, Array<{ verb: string; to: string }>>();
  const targets = new Set<string>();
  for (const r of rels) {
    const list = children.get(r.from_ref) || [];
    list.push({ verb: relVerb(r.type), to: r.to_ref });
    children.set(r.from_ref, list);
    targets.add(r.to_ref);
  }

  const itemRefs = objects.filter((o) => o.type === "Item").map((o) => `${o.type}:${o.id}`);
  const roots = itemRefs.length
    ? itemRefs
    : objects
        .map((o) => `${o.type}:${o.id}`)
        .filter((key) => !targets.has(key));
  const shown = roots.length ? roots : objects.map((o) => `${o.type}:${o.id}`);

  function openKey(key: string) {
    const { type, id } = parseRef(key);
    const obj = objects.find((o) => o.type === type && String(o.id) === id);
    if (obj) onOpen(obj);
  }

  function Node({ objectKey, depth }: { objectKey: string; depth: number }) {
    const { type, id } = parseRef(objectKey);
    const obj = objects.find((o) => o.type === type && String(o.id) === id);
    const kids = children.get(objectKey) || [];
    return (
      <div>
        <button
          type="button"
          className="og-node-btn"
          data-testid={`rel-node-${type}-${id}`}
          onClick={() => openKey(objectKey)}
        >
          <span className="og-type">{typeLabel(type)}</span>
          {obj ? itemLabel(obj) : objectLabel(objects, objectKey)}
        </button>
        {kids.length > 0 && depth < 4 && (
          <div className="og-children">
            {kids.map((k, i) => (
              <div key={`${objectKey}-${k.to}-${i}`}>
                <div className="og-verb">{k.verb}</div>
                <Node objectKey={k.to} depth={depth + 1} />
              </div>
            ))}
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="og-tree" data-testid="relationship-map">
      {shown.map((key) => (
        <Node key={key} objectKey={key} depth={0} />
      ))}
    </div>
  );
}
