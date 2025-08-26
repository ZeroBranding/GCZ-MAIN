from typing import Dict, Any

from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode

from ai.graph.state import GraphState
from ai.graph.nodes.planner import PlannerNode
from ai.graph.nodes.decider import DeciderNode  
from ai.graph.nodes.executor import ExecutorNode
from ai.graph.nodes.reporter import ReporterNode
from ai.graph.tools import get_tool_schemas
from core.logging import logger


class LangGraphOrchestrator:
    """
    LangGraph-basierter Workflow-Orchestrator.
    Koordiniert Planning, Execution und Reporting über Graph-basierte State Machine.
    """
    
    def __init__(self):
        self.graph = self._build_graph()
        self.compiled_graph = None
        
        # Node-Instanzen
        self.planner = PlannerNode()
        self.decider = DeciderNode()
        self.executor = ExecutorNode()
        self.reporter = ReporterNode()
        
        logger.info("LangGraph orchestrator initialized")
    
    def _build_graph(self) -> StateGraph:
        """Erstellt den LangGraph StateGraph."""
        
        # StateGraph mit GraphState als Schema
        graph = StateGraph(GraphState)
        
        # === Nodes hinzufügen ===
        
        # Entry Point: Planner
        graph.add_node("planner", self._planner_node)
        
        # Decision Logic
        graph.add_node("decider", self._decider_node)
        
        # Execution Engine
        graph.add_node("executor", self._executor_node)
        
        # Output/Reporting
        graph.add_node("reporter", self._reporter_node)
        
        # === Edges definieren ===
        
        # Start: Entry point
        graph.set_entry_point("planner")
        
        # Nach Planning: immer zu Decider
        graph.add_edge("planner", "decider")
        
        # Decider: Conditional routing
        graph.add_conditional_edges(
            "decider",
            self._should_continue_execution,
            {
                "execute": "executor",
                "report": "reporter", 
                "end": END
            }
        )
        
        # Nach Execution: zurück zu Decider (für Loop)
        graph.add_edge("executor", "decider")
        
        # Reporter: Final END
        graph.add_edge("reporter", END)
        
        return graph
    
    def compile(self) -> None:
        """Kompiliert den Graph für Ausführung."""
        
        if self.compiled_graph is None:
            self.compiled_graph = self.graph.compile()
            logger.info("LangGraph compiled successfully")
    
    async def execute(self, initial_state: GraphState) -> GraphState:
        """
        Führt den kompletten Workflow aus.
        
        Args:
            initial_state: Startzustand mit user, goal, etc.
            
        Returns:
            final_state: Endzustand mit Ergebnissen
        """
        
        if self.compiled_graph is None:
            self.compile()
        
        logger.info(f"Starting workflow execution for goal: {initial_state.goal}")
        
        try:
            # Graph ausführen
            final_state = await self.compiled_graph.ainvoke(initial_state)
            
            logger.info(f"Workflow completed. Session: {final_state.session_id}")
            return final_state
            
        except Exception as e:
            logger.error(f"Workflow execution failed: {e}", exc_info=True)
            
            # Error State setzen
            initial_state.is_failed = True
            initial_state.add_error(
                message=f"Workflow execution failed: {str(e)}",
                severity="critical"
            )
            
            return initial_state
    
    # === Node Wrapper Functions ===
    
    def _planner_node(self, state: GraphState) -> Dict[str, Any]:
        """Wrapper für PlannerNode."""
        try:
            result = self.planner(state)
            
            # Plan in State übernehmen
            if "plan" in result:
                state.plan = result["plan"]
                state.update_timestamp()
                
            return {"plan": state.plan}
            
        except Exception as e:
            logger.error(f"Planner node failed: {e}")
            state.add_error(f"Planning failed: {str(e)}")
            return {"plan": []}
    
    def _decider_node(self, state: GraphState) -> Dict[str, Any]:
        """Wrapper für DeciderNode."""
        try:
            result = self.decider(state)
            
            # Decision State aktualisieren
            if "next_step" in result and result["next_step"]:
                # Step als current setzen
                current_item = result["next_step"]
                for i, item in enumerate(state.plan):
                    if item.id == current_item.id:
                        state.current_step = i
                        break
            
            return result
            
        except Exception as e:
            logger.error(f"Decider node failed: {e}")
            state.add_error(f"Decision failed: {str(e)}")
            return {
                "next_step": None,
                "should_continue": False,
                "reason": f"Decider error: {str(e)}"
            }
    
    def _executor_node(self, state: GraphState) -> Dict[str, Any]:
        """Wrapper für ExecutorNode."""
        try:
            result = self.executor(state)
            
            # Execution Result in State speichern
            if "execution_result" in result:
                state.last_result = result["execution_result"]
                state.update_timestamp()
            
            return result
            
        except Exception as e:
            logger.error(f"Executor node failed: {e}")
            state.add_error(f"Execution failed: {str(e)}")
            return {
                "execution_result": None,
                "error": f"Executor error: {str(e)}"
            }
    
    def _reporter_node(self, state: GraphState) -> Dict[str, Any]:
        """Wrapper für ReporterNode."""
        try:
            # State als completed markieren
            state.is_completed = True
            state.update_timestamp()
            
            result = self.reporter(state)
            return result
            
        except Exception as e:
            logger.error(f"Reporter node failed: {e}")
            state.add_error(f"Reporting failed: {str(e)}")
            return {
                "report_sent": False,
                "error": f"Reporter error: {str(e)}"
            }
    
    # === Conditional Edge Logic ===
    
    def _should_continue_execution(self, state: GraphState) -> str:
        """
        Entscheidet wohin der Flow nach dem Decider geht.
        
        Returns:
            "execute": Führe nächsten Step aus
            "report": Sende Ergebnis 
            "end": Beende Workflow
        """
        
        # Hole letzte Decision
        current_item = state.get_current_plan_item()
        decider_result = getattr(state, '_last_decider_result', {})
        
        should_continue = decider_result.get('should_continue', False)
        next_step = decider_result.get('next_step')
        reason = decider_result.get('reason', 'Unknown')
        
        logger.debug(f"Continue decision: {should_continue}, reason: {reason}")
        
        # Kritische Fehler: Sofort beenden
        if state.has_critical_errors():
            logger.warning("Critical errors detected, ending workflow")
            return "end"
        
        # Kein nächster Step und sollte nicht fortfahren: Report
        if not should_continue and not next_step:
            logger.info("No more steps, proceeding to report")
            return "report"
        
        # Step vorhanden und sollte fortfahren: Execute
        if should_continue and next_step:
            logger.info(f"Continuing with step: {next_step.action}")
            return "execute"
        
        # Resources nicht verfügbar: Wait/Retry Logic
        if should_continue and not next_step:
            # Für jetzt: ende den Workflow
            # TODO: Implement waiting/retry logic
            logger.warning("Resources not available, ending workflow")
            return "report"
        
        # Fallback: Report
        logger.info("Fallback: proceeding to report")
        return "report"
    
    # === Utility Methods ===
    
    def get_graph_visualization(self) -> str:
        """Gibt Mermaid-Diagramm des Graphs zurück."""
        
        mermaid = """
graph TD
    A[planner] --> B[decider]
    B --> C{Decision}
    C -->|execute| D[executor]
    C -->|report| E[reporter]
    C -->|end| F[END]
    D --> B
    E --> F
    
    style A fill:#e1f5fe
    style B fill:#fff3e0
    style D fill:#f3e5f5
    style E fill:#e8f5e8
    style F fill:#ffebee
"""
        return mermaid
    
    def get_state_summary(self, state: GraphState) -> Dict[str, Any]:
        """Gibt Zusammenfassung des aktuellen State zurück."""
        
        return {
            "session_id": state.session_id,
            "goal": state.goal,
            "current_step": state.current_step,
            "total_steps": len(state.plan),
            "completed_steps": len([item for item in state.plan if item.status == "completed"]),
            "failed_steps": len([item for item in state.plan if item.status == "failed"]),
            "artifacts_count": len(state.artifacts),
            "errors_count": len(state.errors),
            "is_completed": state.is_completed,
            "is_failed": state.is_failed,
            "retry_budget_used": state.used_retries,
            "execution_time": (state.updated_at - state.created_at).total_seconds()
        }


# === Factory Functions ===

def create_orchestrator() -> LangGraphOrchestrator:
    """Factory function für Orchestrator."""
    return LangGraphOrchestrator()


async def execute_workflow(goal: str, user_context: Dict[str, Any]) -> GraphState:
    """
    Convenience function für direkte Workflow-Ausführung.
    
    Args:
        goal: User goal (z.B. "/img a cat in space")
        user_context: User information (user_id, telegram_chat_id, etc.)
        
    Returns:
        final_state: Workflow-Ergebnis
    """
    
    from ai.graph.state import UserContext, UserRole
    
    # Initial State erstellen
    user = UserContext(
        user_id=user_context.get("user_id", "unknown"),
        username=user_context.get("username", "unknown"),
        role=UserRole(user_context.get("role", "user")),
        telegram_chat_id=user_context.get("telegram_chat_id")
    )
    
    initial_state = GraphState(
        user=user,
        goal=goal
    )
    
    # Orchestrator erstellen und ausführen
    orchestrator = create_orchestrator()
    final_state = await orchestrator.execute(initial_state)
    
    return final_state