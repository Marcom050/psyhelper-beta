"""Pure clinical analysis helpers for PsyHelper.

This module deliberately avoids Streamlit/session dependencies: every helper
receives the data it analyzes through explicit arguments.
"""

import pandas as pd


HIGH_RISK_KEYWORDS = [
    "suicidio", "suicid", "farla finita", "non voglio vivere", "uccidermi", "autolesion", "tagliarmi",
    "morire", "overdose", "impicc", "buttarmi", "sparire per sempre",
]

AVOIDANCE_KEYWORDS = ["evito", "evitare", "rimando", "non sono uscito", "annullo", "isolamento", "mi isolo", "scappo"]
CATASTROPHIC_KEYWORDS = ["disastro", "catastrofe", "terribile", "non ce la farò", "andrà malissimo", "rovinerò", "fallirò"]
SOCIAL_KEYWORDS = ["sociale", "persone", "uscire", "gruppo", "festa", "colleghi", "giudicano", "vergogna"]
WORK_KEYWORDS = ["lavoro", "capo", "collega", "scadenza", "ufficio", "riunione", "cliente", "turno"]


def most_common_values(series, limit=3):
    values = []
    for item in series.dropna():
        if isinstance(item, list):
            values.extend(item)
        elif item:
            values.extend([part.strip() for part in str(item).split(",") if part.strip()])
    return pd.Series(values).value_counts().head(limit) if values else pd.Series(dtype="int64")


def text_blob_from_entries(entries):
    fields = ["trigger", "pensiero_automatico", "comportamento", "risposta_alternativa", "nota_professionista", "bisogno"]
    return " ".join(str(entry.get(field, "")) for entry in entries for field in fields).lower()


def keyword_hits(text, keywords):
    return sum(1 for keyword in keywords if keyword in text)


def clinical_snapshot(wellness, messages=None):
    entries = wellness.get("mood_entries", [])
    messages = messages or []
    assignments = wellness.get("homework_assignments", [])
    submissions = wellness.get("homework_submissions", [])
    if entries:
        df = pd.DataFrame(entries)
        df["data"] = pd.to_datetime(df["data"], errors="coerce")
        df = df.dropna(subset=["data"]).sort_values("data")
    else:
        df = pd.DataFrame()

    now = pd.Timestamp.today().normalize()
    last_14 = df[df["data"] >= now - pd.Timedelta(days=14)] if not df.empty else pd.DataFrame()
    prev_14 = df[(df["data"] < now - pd.Timedelta(days=14)) & (df["data"] >= now - pd.Timedelta(days=28))] if not df.empty else pd.DataFrame()
    scope_df = last_14 if not last_14.empty else df

    insights = []
    alerts = []
    if not scope_df.empty:
        avg_anxiety = scope_df["ansia"].mean()
        avg_stress = scope_df["stress"].mean()
        latest = scope_df.iloc[-1]
        if latest.get("ansia", 0) >= 8 or latest.get("umore_intensita", 0) >= 8:
            alerts.append("Forte intensità emotiva recente: potenziale area da attenzionare.")
        if not prev_14.empty and avg_anxiety - prev_14["ansia"].mean() >= 1.5:
            insights.append("Ansia in aumento rispetto alle 2 settimane precedenti.")
        monday_df = df[df["data"].dt.weekday == 0]
        if len(monday_df) >= 2 and monday_df["ansia"].mean() >= df["ansia"].mean() + 1:
            insights.append("Ansia tendenzialmente più alta il lunedì.")
        trigger_counts = most_common_values(scope_df.get("trigger", pd.Series(dtype="object")), limit=3)
        for trigger, count in trigger_counts.items():
            if count >= 2:
                insights.append(f"Trigger ricorrente: {trigger} ({count} rilevazioni).")
        if len(scope_df) <= 1 and len(df) >= 3:
            alerts.append("Riduzione delle compilazioni recenti: possibile rischio drop-out o calo aderenza.")
        last_entry_date = df["data"].max() if not df.empty else None
        if last_entry_date is not None and (now - last_entry_date.normalize()).days >= 7:
            alerts.append("Nessuna compilazione negli ultimi 7 giorni: verificare engagement.")
    else:
        avg_anxiety = avg_stress = 0
        alerts.append("Nessuna scheda compilata: aderenza non valutabile.")

    text_blob = text_blob_from_entries(entries) + " " + " ".join(str(m.get("content", "")) for m in messages).lower()
    if keyword_hits(text_blob, HIGH_RISK_KEYWORDS):
        alerts.append("Parole ad alto rischio rilevate: potenziale area da attenzionare, senza diagnosi automatica.")
    if keyword_hits(text_blob, CATASTROPHIC_KEYWORDS) >= 2:
        insights.append("Pensieri catastrofici ricorrenti nel materiale scritto.")
    if keyword_hits(text_blob, AVOIDANCE_KEYWORDS) >= 2:
        insights.append("Indicatori di evitamento in aumento o ricorrenti.")
    if keyword_hits(text_blob, SOCIAL_KEYWORDS) >= 2:
        insights.append("Temi sociali/interpersonali ricorrenti.")
    if keyword_hits(text_blob, WORK_KEYWORDS) >= 2:
        insights.append("Trigger legati al lavoro ricorrenti.")

    completed_ids = {submission.get("assignment_id") for submission in submissions}
    total_assignments = len(assignments)
    completed_assignments = len([a for a in assignments if a.get("id") in completed_ids or a.get("status") == "completato"])
    overdue = []
    for assignment in assignments:
        due_date = assignment.get("due_date")
        if assignment.get("id") in completed_ids:
            continue
        if due_date and pd.to_datetime(due_date, errors="coerce") < now:
            overdue.append(assignment)
    if overdue:
        alerts.append(f"{len(overdue)} homework assegnati risultano oltre scadenza.")

    return {
        "entries_count": len(scope_df),
        "avg_anxiety": avg_anxiety,
        "avg_stress": avg_stress,
        "insights": insights[:6] or ["Servono più dati recenti per generare pattern affidabili."],
        "alerts": alerts[:6],
        "homework_total": total_assignments,
        "homework_completed": completed_assignments,
        "homework_compliance": (completed_assignments / total_assignments * 100) if total_assignments else 0,
        "last_activity": df["data"].max().date().isoformat() if not df.empty else "—",
        "scope_df": scope_df,
    }


def weekly_recap(snapshot):
    return [
        f"Schede ultime 2 settimane: {snapshot['entries_count']}",
        f"Ansia media: {snapshot['avg_anxiety']:.1f}/10",
        f"Stress medio: {snapshot['avg_stress']:.1f}/10",
        f"Homework completati: {snapshot['homework_completed']} su {snapshot['homework_total']} ({snapshot['homework_compliance']:.0f}%)",
        *snapshot["insights"][:4],
    ]


def build_timeline_events(wellness):
    events = []
    for entry in wellness.get("mood_entries", []):
        events.append({
            "data": entry.get("data", entry.get("creata_il", "")),
            "tipo": "Diario",
            "titolo": f"{entry.get('umore', 'Umore')} · ansia {entry.get('ansia', '—')}/10",
            "dettaglio": entry.get("trigger") or entry.get("pensiero_automatico") or "Scheda CBT compilata",
        })
    for assignment in wellness.get("homework_assignments", []):
        events.append({
            "data": assignment.get("assigned_at", ""),
            "tipo": "Homework assegnato",
            "titolo": assignment.get("template", "Homework"),
            "dettaglio": assignment.get("instructions", ""),
        })
    for submission in wellness.get("homework_submissions", []):
        events.append({
            "data": submission.get("submitted_at", ""),
            "tipo": "Homework completato",
            "titolo": submission.get("template", "Homework"),
            "dettaglio": submission.get("summary", ""),
        })
    events.extend(wellness.get("timeline_events", []))
    return sorted(events, key=lambda item: str(item.get("data", "")), reverse=True)
