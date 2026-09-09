"use client";

import { Plus } from "lucide-react";
import Link from "next/link";
import React from "react";

import { useCapabilities } from "@/components/hooks";
import { Button, Card, Drawer } from "@/components/ui";
import { endpoints } from "@/lib/api";

/**
 * Listing a property.
 *
 * The form collects what the seller *asserts*, and says so. A new listing starts
 * with every core claim at PENDING and a transaction that cannot progress: the
 * platform has been told about a property, not shown evidence of one. It is also
 * put straight onto a verifier's desk, so no file exists without somebody
 * accountable for it.
 */
export function ListPropertyButton({ onCreated }: { onCreated: () => void }) {
  const caps = useCapabilities();
  const may = caps.can("LIST_PROPERTY");
  const [open, setOpen] = React.useState(false);
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState("");
  const [done, setDone] = React.useState<any>(null);
  const [form, setForm] = React.useState({
    survey_number: "",
    district: "",
    village: "",
    property_type: "Residential Plot",
    claimed_area_sqft: "",
    guideline_value_inr: "",
    asking_price_inr: "",
    listed_owner_name: "",
  });

  const set = (k: string, v: string) => setForm((f) => ({ ...f, [k]: v }));

  const submit = async () => {
    setBusy(true);
    setError("");
    try {
      const res = await endpoints.createProperty({
        ...form,
        claimed_area_sqft: Number(form.claimed_area_sqft) || 0,
        guideline_value_inr: Number(form.guideline_value_inr) || 0,
        asking_price_inr: Number(form.asking_price_inr) || 0,
      });
      setDone(res);
      onCreated();
    } catch (e: any) {
      setError(e?.detail || "Could not list the property.");
    } finally {
      setBusy(false);
    }
  };

  const ready =
    form.survey_number && form.district && form.village &&
    form.listed_owner_name && Number(form.claimed_area_sqft) > 0;

  return (
    <>
      <Button
        size="sm"
        onClick={() => { setOpen(true); setDone(null); setError(""); }}
        disabled={!may}
        title={may ? undefined : caps.why("LIST_PROPERTY")}
      >
        <Plus className="h-3.5 w-3.5" />
        List a property
      </Button>

      <Drawer
        open={open}
        onClose={() => setOpen(false)}
        title="List a property for sale"
        subtitle="Everything here is recorded as the seller's claim. Nothing is verified until documents support it."
      >
        {done ? (
          <div className="space-y-3 p-5">
            <Card className="bg-status-verifiedBg p-4 ring-1 ring-status-verified/20">
              <p className="text-sm font-semibold text-ink">
                {done.reference} created
              </p>
              <p className="mt-1 text-[13px] leading-relaxed text-ink-muted">{done.notice}</p>
              {done.assigned_verifier ? (
                <p className="mt-2 text-2xs text-ink-subtle">
                  Assigned to verifier{" "}
                  <span className="font-medium text-ink">{done.assigned_verifier.name}</span> —
                  it is already on their desk.
                </p>
              ) : null}
            </Card>
            <Link href="/documents">
              <Button size="sm">Upload evidence for it</Button>
            </Link>
          </div>
        ) : (
          <div className="space-y-3 p-5">
            {error ? (
              <Card className="border-status-conflicting/30 bg-status-conflictingBg p-3.5">
                <p className="text-[13px] text-status-conflicting">{error}</p>
              </Card>
            ) : null}
            {[
              ["listed_owner_name", "Owner name, as you are listing it", "text"],
              ["survey_number", "Survey number", "text"],
              ["village", "Village", "text"],
              ["district", "District", "text"],
              ["property_type", "Property type", "text"],
              ["claimed_area_sqft", "Claimed area (sq.ft)", "number"],
              ["guideline_value_inr", "Guideline value (INR)", "number"],
              ["asking_price_inr", "Asking price (INR)", "number"],
            ].map(([key, label, type]) => (
              <div key={key}>
                <label className="section-label mb-1 block" htmlFor={key}>{label}</label>
                <input
                  id={key}
                  type={type}
                  value={(form as any)[key]}
                  onChange={(e) => set(key, e.target.value)}
                  className="w-full rounded-lg border border-canvas-border bg-canvas-raised px-3 py-2 text-[13px] text-ink outline-none focus:border-navy-400"
                />
              </div>
            ))}
            <p className="text-2xs leading-relaxed text-ink-subtle">
              The name you list is stored separately from any owner name the documents
              establish. That separation is what lets the platform notice if the two disagree.
            </p>
            <div className="flex gap-2 pt-1">
              <Button onClick={submit} disabled={busy || !ready}>
                {busy ? "Listing…" : "List the property"}
              </Button>
              <Button variant="secondary" onClick={() => setOpen(false)}>Cancel</Button>
            </div>
          </div>
        )}
      </Drawer>
    </>
  );
}
