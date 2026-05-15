"""Orkestrator LangGraph untuk alur Laksa."""

from __future__ import annotations

from typing import Any, List, TypedDict

from langgraph.graph import END, StateGraph

from agents.advisor import AdvisorAgent
from agents.analyzer import AnalyzerAgent
from agents.collector import CollectorAgent
from agents.reporter import ReporterAgent


class LaksaState(TypedDict, total=False):
    """State yang mengalir antar agen."""

    business_id: int
    trigger: str
    tanggal_laporan: Any
    nomor_peer_whatsapp: str
    lewati_wa_laporan: bool
    raw_transactions: list
    normalized_transactions: list
    analysis_result: dict
    recommendations: str
    report_id: int
    whatsapp_sent: bool
    path_pdf: str
    errors: List[str]


def create_laksa_graph():
    """Membangun StateGraph utama."""
    graph = StateGraph(LaksaState)

    pengumpul = CollectorAgent()
    penganalisis = AnalyzerAgent()
    penasihat = AdvisorAgent()
    pelapor = ReporterAgent()

    graph.add_node("collect", pengumpul.run)
    graph.add_node("analyze", penganalisis.run)
    graph.add_node("advise", penasihat.run)
    graph.add_node("report", pelapor.run)

    graph.set_entry_point("collect")
    graph.add_edge("collect", "analyze")
    graph.add_edge("analyze", "advise")
    graph.add_edge("advise", "report")
    graph.add_edge("report", END)

    return graph.compile()


# Singleton untuk dipakai di seluruh app
laksa_agent = create_laksa_graph()
