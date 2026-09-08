"""
Temporal ownership knowledge graph.

Nodes and edges are derived from the ownership-event ledger, the document set and
the claim/contradiction records, then served through a small `GraphStore`
abstraction.  The default implementation materialises the graph from SQL rows; a
Neo4j-backed implementation can be substituted without changing the API or the UI
(build brief §26: do not require Neo4j to demonstrate the concept).

The graph is *temporal*: every edge carries the date it became true and, where
known, the date it stopped being true.  That is what lets the UI show ownership as
a chain through time rather than a single current-owner field, and what lets the
system say "this power of attorney was valid when the deed was executed" — or that
it was not.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from datetime import date, datetime

from ...domain import (
    ClaimType,
    ContradictionType,
    DocumentType,
    EdgeType,
    NodeType,
    OwnershipEventType,
)


@dataclass
class GraphNode:
    id: str
    type: str
    label: str
    sublabel: str = ""
    date: str | None = None
    status: str = "NEUTRAL"          # VERIFIED | CONFLICTING | EXPIRED | NEUTRAL | CURRENT
    evidence: list[dict] = field(default_factory=list)
    meta: dict = field(default_factory=dict)

    def dict(self) -> dict:
        return asdict(self)


@dataclass
class GraphEdge:
    id: str
    source: str
    target: str
    type: str
    label: str = ""
    valid_from: str | None = None
    valid_to: str | None = None
    status: str = "NEUTRAL"
    evidence: list[dict] = field(default_factory=list)

    def dict(self) -> dict:
        return asdict(self)


@dataclass
class TimelineEntry:
    date: str
    year: int
    title: str
    description: str
    event_type: str
    status: str = "NEUTRAL"
    evidence: list[dict] = field(default_factory=list)


@dataclass
class OwnershipGraph:
    nodes: list[GraphNode] = field(default_factory=list)
    edges: list[GraphEdge] = field(default_factory=list)
    timeline: list[TimelineEntry] = field(default_factory=list)
    current_owner: str | None = None
    chain_complete: bool = True
    chain_note: str = ""

    def dict(self) -> dict:
        return {
            "nodes": [n.dict() for n in self.nodes],
            "edges": [e.dict() for e in self.edges],
            "timeline": [asdict(t) for t in self.timeline],
            "current_owner": self.current_owner,
            "chain_complete": self.chain_complete,
            "chain_note": self.chain_note,
        }


class GraphStore(ABC):
    """Storage-agnostic seam so Neo4j can be introduced in Review-3."""

    @abstractmethod
    def build(self, property_obj, documents, claims, events, contradictions) -> OwnershipGraph:
        ...


def _slug(text: str) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in (text or "").strip().lower())[:48]


def _iso(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


class SqlGraphStore(GraphStore):
    """Materialises the ownership graph from the relational store."""

    def build(self, property_obj, documents, claims, events, contradictions) -> OwnershipGraph:
        graph = OwnershipGraph()
        docs_by_id = {d.id: d for d in documents}
        seen_nodes: set[str] = set()

        def add_node(node: GraphNode) -> str:
            if node.id not in seen_nodes:
                seen_nodes.add(node.id)
                graph.nodes.append(node)
            return node.id

        def person_node(name: str, status: str = "NEUTRAL", evidence=None) -> str:
            nid = f"person::{_slug(name)}"
            if nid in seen_nodes:
                # upgrade status if a stronger one arrives
                for n in graph.nodes:
                    if n.id == nid and status != "NEUTRAL":
                        n.status = status if n.status == "NEUTRAL" else n.status
                return nid
            return add_node(
                GraphNode(nid, NodeType.PERSON.value, name, "Person",
                          status=status, evidence=evidence or [])
            )

        # --- the parcel ------------------------------------------------------
        prop_id = add_node(
            GraphNode(
                f"property::{property_obj.id}",
                NodeType.PROPERTY.value,
                f"Survey {property_obj.survey_number}",
                f"{property_obj.village}, {property_obj.district}",
                status="CURRENT",
                meta={
                    "reference": property_obj.reference,
                    "area": property_obj.claimed_area_sqft,
                    "type": property_obj.property_type,
                },
            )
        )

        # --- documents -------------------------------------------------------
        doc_node_type = {
            DocumentType.SALE_DEED.value: NodeType.DEED.value,
            DocumentType.MORTGAGE_DOCUMENT.value: NodeType.MORTGAGE.value,
            DocumentType.POWER_OF_ATTORNEY.value: NodeType.POWER_OF_ATTORNEY.value,
            DocumentType.TAX_RECEIPT.value: NodeType.TAX_RECORD.value,
            DocumentType.SURVEY_RECORD.value: NodeType.SURVEY_RECORD.value,
        }
        for doc in documents:
            if doc.is_pending_evidence:
                continue
            ntype = doc_node_type.get(doc.doc_type)
            if not ntype:
                continue
            status = "EXPIRED" if doc.is_expired else "NEUTRAL"
            if any(f.get("severity") == "HIGH" for f in (doc.integrity_flags or [])):
                status = "CONFLICTING"
            nid = add_node(
                GraphNode(
                    f"doc::{doc.id}",
                    ntype,
                    doc.doc_type.replace("_", " ").title(),
                    doc.filename,
                    date=_iso(doc.issued_on),
                    status=status,
                    evidence=[{"document_id": doc.id, "filename": doc.filename, "page": 1}],
                    meta={"doc_type": doc.doc_type, "expired": doc.is_expired},
                )
            )
            graph.edges.append(
                GraphEdge(
                    f"e::{doc.id}::recorded",
                    nid,
                    prop_id,
                    EdgeType.RECORDED_IN.value,
                    "records",
                    valid_from=_iso(doc.issued_on),
                    status=status,
                )
            )

        # --- ownership chain from the event ledger ---------------------------
        ordered = sorted(events, key=lambda e: e.occurred_on)
        conflicting_owner = any(
            c.contradiction_type == ContradictionType.OWNER_IDENTITY.value and not c.resolved
            for c in contradictions
        )

        previous_owner_node: str | None = None
        for ev in ordered:
            ev_date = _iso(ev.occurred_on)
            evidence = []
            if ev.evidence_document_id and ev.evidence_document_id in docs_by_id:
                d = docs_by_id[ev.evidence_document_id]
                evidence = [{"document_id": d.id, "filename": d.filename,
                             "page": ev.evidence_page}]

            if ev.event_type in {
                OwnershipEventType.ORIGINAL_GRANT.value,
                OwnershipEventType.TRANSFER.value,
                OwnershipEventType.SALE_DEED_REGISTERED.value,
                OwnershipEventType.PARTITION.value,
            }:
                to_node = person_node(
                    ev.to_party or "Unknown party",
                    "CONFLICTING" if (conflicting_owner and ev is ordered[-1]) else "NEUTRAL",
                    evidence,
                )
                if ev.from_party:
                    from_node = person_node(ev.from_party, evidence=evidence)
                    graph.edges.append(
                        GraphEdge(
                            f"e::{ev.id}::transfer",
                            from_node,
                            to_node,
                            EdgeType.TRANSFERRED_TO.value,
                            f"transferred {ev.occurred_on:%Y}",
                            valid_from=ev_date,
                            status="CONFLICTING" if ev.is_disputed else "NEUTRAL",
                            evidence=evidence,
                        )
                    )
                graph.edges.append(
                    GraphEdge(
                        f"e::{ev.id}::owns",
                        to_node,
                        prop_id,
                        EdgeType.OWNS.value if ev is ordered[-1] else EdgeType.OWNED.value,
                        "owns" if ev is ordered[-1] else "owned",
                        valid_from=ev_date,
                        status="CONFLICTING" if ev.is_disputed else "NEUTRAL",
                        evidence=evidence,
                    )
                )
                previous_owner_node = to_node
                graph.current_owner = ev.to_party

            elif ev.event_type == OwnershipEventType.MORTGAGE_CREATED.value:
                m_id = add_node(
                    GraphNode(
                        f"mortgage::{ev.id}",
                        NodeType.MORTGAGE.value,
                        ev.counterparty or "Mortgage",
                        f"₹{ev.amount_inr:,.0f}" if ev.amount_inr else "Charge created",
                        date=ev_date,
                        status="CONFLICTING",
                        evidence=evidence,
                    )
                )
                graph.edges.append(
                    GraphEdge(
                        f"e::{ev.id}::mortgaged",
                        prop_id,
                        m_id,
                        EdgeType.MORTGAGED_TO.value,
                        "charged to",
                        valid_from=ev_date,
                        status="CONFLICTING",
                        evidence=evidence,
                    )
                )
            elif ev.event_type == OwnershipEventType.MORTGAGE_RELEASED.value:
                for edge in graph.edges:
                    if edge.type == EdgeType.MORTGAGED_TO.value and edge.valid_to is None:
                        edge.valid_to = ev_date
                        edge.status = "NEUTRAL"
                for node in graph.nodes:
                    if node.type == NodeType.MORTGAGE.value and node.status == "CONFLICTING":
                        node.status = "NEUTRAL"
                        node.sublabel += " — released"
            elif ev.event_type in {
                OwnershipEventType.POA_GRANTED.value, OwnershipEventType.POA_EXPIRED.value
            }:
                holder = ev.to_party or "Attorney holder"
                grantor = ev.from_party or "Principal"
                expired = ev.event_type == OwnershipEventType.POA_EXPIRED.value
                p_id = add_node(
                    GraphNode(
                        f"poa::{ev.id}",
                        NodeType.POWER_OF_ATTORNEY.value,
                        "Power of Attorney",
                        f"{grantor} → {holder}",
                        date=ev_date,
                        status="EXPIRED" if expired else "NEUTRAL",
                        evidence=evidence,
                    )
                )
                g_node = person_node(grantor, evidence=evidence)
                h_node = person_node(holder, "CONFLICTING" if expired else "NEUTRAL", evidence)
                graph.edges.append(
                    GraphEdge(f"e::{ev.id}::granted", g_node, p_id,
                              EdgeType.AUTHORIZED.value, "granted",
                              valid_from=ev_date, status="EXPIRED" if expired else "NEUTRAL",
                              evidence=evidence)
                )
                graph.edges.append(
                    GraphEdge(f"e::{ev.id}::holder", p_id, h_node,
                              EdgeType.AUTHORIZED.value,
                              "authorises (expired)" if expired else "authorises",
                              valid_from=ev_date, valid_to=ev_date if expired else None,
                              status="EXPIRED" if expired else "NEUTRAL", evidence=evidence)
                )
            elif ev.event_type == OwnershipEventType.TAX_PAID.value and previous_owner_node:
                t_id = add_node(
                    GraphNode(f"tax::{ev.id}", NodeType.TAX_RECORD.value, "Property Tax",
                              ev.description or "Paid", date=ev_date, evidence=evidence)
                )
                graph.edges.append(
                    GraphEdge(f"e::{ev.id}::tax", t_id, prop_id,
                              EdgeType.SUPPORTED_BY.value, "assessed on",
                              valid_from=ev_date, evidence=evidence)
                )

        # --- listing party, when it differs from the evidenced chain ---------
        listed = (property_obj.listed_owner_name or "").strip()
        if listed and conflicting_owner:
            l_node = person_node(listed, "CONFLICTING")
            graph.edges.append(
                GraphEdge(
                    "e::listing::claims",
                    l_node,
                    prop_id,
                    EdgeType.CONTRADICTS.value,
                    "claims ownership (unsupported)",
                    status="CONFLICTING",
                )
            )
            graph.chain_complete = False
            graph.chain_note = (
                f"The listing party '{listed}' does not appear in the evidenced ownership chain. "
                "The chain shown is the one the documents support."
            )

        # --- contradiction edges ---------------------------------------------
        for c in contradictions:
            if c.resolved or not (c.left_claim_id and c.right_claim_id):
                continue
            claims_by_id = {cl.id: cl for cl in claims}
            left, right = claims_by_id.get(c.left_claim_id), claims_by_id.get(c.right_claim_id)
            if not (left and right and left.document_id and right.document_id):
                continue
            src, dst = f"doc::{left.document_id}", f"doc::{right.document_id}"
            if src not in seen_nodes or dst not in seen_nodes:
                continue
            graph.edges.append(
                GraphEdge(
                    f"e::contra::{c.id}",
                    src,
                    dst,
                    EdgeType.CONTRADICTS.value,
                    f"{c.claim_type.replace('_', ' ')} conflict",
                    status="CONFLICTING",
                    evidence=[{"contradiction_id": c.id, "explanation": c.explanation}],
                )
            )

        graph.timeline = self._timeline(ordered, docs_by_id, contradictions)
        if not ordered:
            graph.chain_complete = False
            graph.chain_note = (
                "No ownership events could be derived from the evidence on file, so no chain of "
                "title can be shown."
            )
        return graph

    def _timeline(self, events, docs_by_id, contradictions) -> list[TimelineEntry]:
        titles = {
            OwnershipEventType.ORIGINAL_GRANT.value: "Original ownership recorded",
            OwnershipEventType.TRANSFER.value: "Ownership transferred",
            OwnershipEventType.SALE_DEED_REGISTERED.value: "Sale deed registered",
            OwnershipEventType.MORTGAGE_CREATED.value: "Mortgage created",
            OwnershipEventType.MORTGAGE_RELEASED.value: "Mortgage released",
            OwnershipEventType.POA_GRANTED.value: "Power of attorney granted",
            OwnershipEventType.POA_EXPIRED.value: "Power of attorney expired",
            OwnershipEventType.TAX_PAID.value: "Property tax paid",
            OwnershipEventType.VERIFICATION_RUN.value: "Evidence verification run",
            OwnershipEventType.PARTITION.value: "Partition recorded",
        }
        out: list[TimelineEntry] = []
        for ev in events:
            evidence = []
            if ev.evidence_document_id and ev.evidence_document_id in docs_by_id:
                d = docs_by_id[ev.evidence_document_id]
                evidence = [{"document_id": d.id, "filename": d.filename,
                             "page": ev.evidence_page}]
            status = "CONFLICTING" if ev.is_disputed else "NEUTRAL"
            if ev.event_type == OwnershipEventType.POA_EXPIRED.value:
                status = "EXPIRED"
            out.append(
                TimelineEntry(
                    date=_iso(ev.occurred_on) or "",
                    year=ev.occurred_on.year,
                    title=titles.get(ev.event_type, ev.event_type.replace("_", " ").title()),
                    description=ev.description
                    or (f"{ev.from_party} → {ev.to_party}" if ev.from_party else (ev.to_party or "")),
                    event_type=ev.event_type,
                    status=status,
                    evidence=evidence,
                )
            )
        return out


class Neo4jGraphStore(GraphStore):  # pragma: no cover - Review-3 seam
    """
    Placeholder for a property-graph database backend.

    Deliberately not implemented: the brief requires that the concept be
    demonstrable without Neo4j. The `build` signature is identical, so switching
    backends is a one-line change in `get_graph_store()`.
    """

    def __init__(self, uri: str, user: str, password: str):
        self.uri, self.user, self.password = uri, user, password

    def build(self, property_obj, documents, claims, events, contradictions) -> OwnershipGraph:
        raise NotImplementedError(
            "Review-3 scope: MERGE nodes/edges into Neo4j and answer chain-of-title queries "
            "with Cypher. The SqlGraphStore produces the same OwnershipGraph shape today."
        )


_store: GraphStore = SqlGraphStore()


def get_graph_store() -> GraphStore:
    return _store
