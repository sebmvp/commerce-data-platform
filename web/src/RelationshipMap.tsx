import type { ContextBundle, ContextObject } from "./types";
import { objectLabel, parseRef, relVerb } from "./ui";

export function RelationshipMap({
  bundle,
  onOpen,
}: {
  bundle: ContextBundle;
  onOpen: (obj: ContextObject) => void;
}) {
  const rels = bundle.relationships || [];
  if (!rels.length) return <p className="lede">No relationships assembled.</p>;
  return (
    <div className="rel-map" data-testid="relationship-map">
      {rels.map((r, i) => {
        const from = parseRef(r.from_ref);
        const to = parseRef(r.to_ref);
        return (
          <div key={`${r.from_ref}-${r.type}-${r.to_ref}-${i}`} className="rel-row">
            <button
              className="rel-node"
              data-testid={`rel-node-${from.type}-${from.id}`}
              onClick={() => {
                const obj = bundle.objects.find(
                  (o) => o.type === from.type && String(o.id) === from.id,
                );
                if (obj) onOpen(obj);
              }}
            >
              {objectLabel(bundle.objects, r.from_ref)}
            </button>
            <span className="rel-verb">{relVerb(r.type)}</span>
            <button
              className="rel-node"
              data-testid={`rel-node-${to.type}-${to.id}`}
              onClick={() => {
                const obj = bundle.objects.find(
                  (o) => o.type === to.type && String(o.id) === to.id,
                );
                if (obj) onOpen(obj);
              }}
            >
              {objectLabel(bundle.objects, r.to_ref)}
            </button>
          </div>
        );
      })}
    </div>
  );
}
