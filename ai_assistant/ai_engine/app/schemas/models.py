from typing import List, Dict, Optional
from pydantic import BaseModel, Field
from typing_extensions import TypedDict
from typing import List, Dict, Optional, TypedDict, Any


class AgentRoutingDecision(BaseModel):
    """Which agents should run for this query."""
    needs_design: bool = Field(False, description="User asks for a solution/architecture/design.")
    needs_technical: bool = Field(False, description="User asks for technical specifications or product info.")
    needs_pricing: bool = Field(False, description="User asks for prices/costs/quotes.")

    # Comparação
    needs_comparison: bool = Field(False, description="User asks to compare X vs Y or differences between products.")

    # Compatibilidade & Lifecycle
    needs_compatibility: bool = Field(False, description="User asks if X works with Y / compatibility.")
    needs_lifecycle: bool = Field(False, description="User asks about EoL/EoS/successor/replacement.")

    # Reservados p/ futuras fases
    needs_recommendation: bool = Field(False, description="User asks for best/choose/recommend (no explicit SKU).")
    needs_tco: bool = Field(False, description="User asks about TCO over N years.")


class SolutionComponent(BaseModel):
    part_number: str = Field(..., description="Exact Cisco SKU.")
    quantity: int = Field(..., description="Units required.")
    role: str = Field(..., description="Function of this component in the solution.")


class SolutionDesign(BaseModel):
    summary: str = Field(..., description="Brief summary; ideally starts with scenario label (e.g., 'Option Cost-Effective:').")
    justification: str = Field(..., description="Why these components were chosen.")
    components: List[SolutionComponent]


class ThreeScenarios(BaseModel):
    """Exactly 3 SolutionDesigns for a single requirement."""
    scenarios: List[SolutionDesign] = Field(..., description="List of exactly 3 SolutionDesign items.")

    @classmethod
    def __get_validators__(cls):
        # pydantic v1 fallback compat
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if isinstance(v, dict) and "scenarios" in v:
            items = v["scenarios"]
            if not isinstance(items, list) or len(items) == 0:
                raise ValueError("scenarios must be a non-empty list")
        return v


class AgentState(TypedDict, total=False):
    # Entrada
    user_query: str
    orchestrator_decision: "AgentRoutingDecision"

    # --- ADICIONE ESTAS DUAS LINHAS ---
    product_context: List[Dict[str, str]]
    base_product_sku: Optional[str]
    # --- FIM DA ADIÇÃO ---

    # Client awareness
    active_client_id: Optional[str]
    client_context: Dict
    client_ack_message: str

    # Contexto técnico (produtos recuperados)
    technical_results: List[Dict]

    # Designer retorna múltiplas opções
    solution_designs: List["SolutionDesign"]

    sku_quantities: Dict[str, int]

    # Validação & regras
    integrity_errors: List[str]
    rule_errors: List[str]

    # Pricing: por bucket (ex.: por cenário) -> lista de itens
    pricing_results: Dict[str, List[dict]]

    # Comparação
    comparison_results: Dict[str, Dict]

    # Compatibilidade & lifecycle
    compatibility_results: Dict[str, Dict]
    lifecycle_info: Dict[str, Dict]

    # --- AQUI ESTÁ FALTANDO ---
    ea: Dict[str, Any]
    ea_pricing_preview: Dict[str, Any]
    # --- FIM DA ADIÇÃO ---

    # NBA + resposta final
    next_best_action: str
    final_response: str

