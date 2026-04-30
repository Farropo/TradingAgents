from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.ledger.store import LedgerStore


def test_graph_records_decision_link_without_blocking_analysis(tmp_path):
    graph = TradingAgentsGraph.__new__(TradingAgentsGraph)
    graph.ledger_store = LedgerStore(tmp_path / "ledger.sqlite")

    graph._record_ledger_decision(
        ticker="NVDA",
        trade_date="2026-01-15",
        rating="Buy",
        final_trade_decision="**Rating**: Buy",
        state_log_path=tmp_path / "state.json",
    )

    decisions = graph.ledger_store.list_decisions()
    assert len(decisions) == 1
    assert decisions[0]["ticker"] == "NVDA"
    assert decisions[0]["rating"] == "Buy"
