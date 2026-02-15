"""Team Leader (Orchestrator): LangGraph state graph that coordinates all agents."""

from langgraph.graph import StateGraph, START, END

from app.agents.state import TradingState
from app.agents.nodes.market_analyst import market_analyst_node
from app.agents.nodes.strategy_search import strategy_search_node
from app.agents.nodes.risk_manager import risk_manager_node
from app.agents.nodes.human_approval import human_approval_node
from app.agents.nodes.execution import execution_node
from app.agents.nodes.monitor import monitor_node
from app.agents.nodes.recipe_evaluator import recipe_evaluator_node


def should_search_strategies(state: TradingState) -> str:
    """After market analysis, decide whether to search or evaluate recipes."""
    # If user has active recipes, evaluate them instead of searching
    if state.get("active_recipes"):
        return "recipe_evaluator"
    regime = state.get("market_regime")
    if regime and regime.get("classification") == "crisis":
        return "risk_manager"
    if state.get("strategy_candidates"):
        return "risk_manager"
    return "strategy_search"


def should_approve(state: TradingState) -> str:
    """After risk assessment, route through human approval if HITL is enabled."""
    risk = state.get("risk_assessment")
    if not risk or not risk.get("approved_trades"):
        return "monitor"
    if state.get("hitl_enabled", False):
        return "human_approval"
    return "execution"


def after_approval(state: TradingState) -> str:
    """After human approval check, decide next step."""
    if state.get("pending_approval"):
        # Waiting for user — stop the graph (will resume on approval)
        return END
    risk = state.get("risk_assessment")
    if not risk or not risk.get("approved_trades"):
        return "monitor"
    return "execution"


def should_continue_loop(state: TradingState) -> str:
    """After monitoring, decide whether to loop back or end."""
    if state.get("error_state"):
        return END
    if not state.get("should_continue", True):
        return END
    if state.get("iteration_count", 0) >= 100:
        return END
    return "market_analyst"


def build_trading_graph(checkpointer=None):
    """Build and compile the trading orchestration graph.

    Flow:
        START → Market Analyst → (Strategy Search | Risk Manager)
              → Risk Manager → (Human Approval | Execution | Monitor)
              → Human Approval → (Execution | Monitor | END)
              → Execution → Monitor → (loop back | END)
    """
    graph = StateGraph(TradingState)

    # Add agent nodes
    graph.add_node("market_analyst", market_analyst_node)
    graph.add_node("strategy_search", strategy_search_node)
    graph.add_node("recipe_evaluator", recipe_evaluator_node)
    graph.add_node("risk_manager", risk_manager_node)
    graph.add_node("human_approval", human_approval_node)
    graph.add_node("execution", execution_node)
    graph.add_node("monitor", monitor_node)

    # Define edges
    graph.add_edge(START, "market_analyst")

    graph.add_conditional_edges(
        "market_analyst",
        should_search_strategies,
        {
            "strategy_search": "strategy_search",
            "recipe_evaluator": "recipe_evaluator",
            "risk_manager": "risk_manager",
        },
    )

    graph.add_edge("strategy_search", "risk_manager")
    graph.add_edge("recipe_evaluator", "risk_manager")

    graph.add_conditional_edges(
        "risk_manager",
        should_approve,
        {
            "human_approval": "human_approval",
            "execution": "execution",
            "monitor": "monitor",
        },
    )

    graph.add_conditional_edges(
        "human_approval",
        after_approval,
        {"execution": "execution", "monitor": "monitor", END: END},
    )

    graph.add_edge("execution", "monitor")

    graph.add_conditional_edges(
        "monitor",
        should_continue_loop,
        {"market_analyst": "market_analyst", END: END},
    )

    return graph.compile(checkpointer=checkpointer)
