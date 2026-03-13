from typing import List, Literal, Optional, Dict
from pydantic import BaseModel, Field, root_validator
import math

# --- Visual Mappings ---
CATEGORY_COLORS: Dict[str, str] = {
    "Architecture": "#60a5fa", # Blue 400
    "System Overview": "#60a5fa", 
    "Testing": "#4ade80", # Green 400
    "Test": "#4ade80",
    "Security": "#f87171", # Red 400
    "Build and Run": "#c084fc", # Purple 400
    "Build & Run": "#c084fc",
    "Impl. Details": "#e879f9", # Fuchsia 400
    "Implementation Details": "#e879f9",
    "Documentation": "#94a3b8" # Slate 400
}

DEFAULT_CATEGORY_COLOR = "#94a3b8"
MUST_COLOR = "#ef4444"
SHOULD_COLOR = "#eab308"
ROOT_COLOR = "#1e293b"


# --- Domain Entities ---

class RuleContent(BaseModel):
    text: str
    originalHeader: str

class RuleMetadata(BaseModel):
    strength: Literal["MUST", "SHOULD"]
    format: Literal["ListItem", "Paragraph"]

class AgentRule(BaseModel):
    """Leaf node representing an actionable rule/instruction."""
    id: str
    type: Literal["rule"] = "rule"
    content: RuleContent
    metadata: RuleMetadata
    
    # Optional parent reference injected during tree building for uniqueness mapping if needed
    parent_id: Optional[str] = None

    @property
    def graph_id(self) -> str:
        """Globally unique ID for the graph rendering to prevent collision."""
        if self.parent_id:
            return f"{self.parent_id}_{self.id}"
        return self.id

    @property
    def color(self) -> str:
        return MUST_COLOR if self.metadata.strength == "MUST" else SHOULD_COLOR

    @property
    def force_graph_radius(self) -> int:
        return 8 if self.metadata.strength == "MUST" else 6
        
    @property
    def tree_graph_radius(self) -> int:
        return 6

    @property
    def short_label(self) -> str:
        text = self.content.text
        return text[:30] + "..." if len(text) > 30 else text
        
    @property
    def html_details(self) -> str:
        return f"""
            <strong>{self.metadata.strength}</strong><br><br>
            {self.content.text}<br><br>
            <hr>
            <small>
            <strong>Original Header:</strong> {self.content.originalHeader}<br>
            <strong>Format:</strong> {self.metadata.format}<br>
            <strong>ID:</strong> {self.id}
            </small>
            """

class RuleCategory(BaseModel):
    """Intermediate node representing a semantic grouping of rules."""
    id: str
    label: str
    type: Literal["category"] = "category"
    count: int
    children: List[AgentRule] = Field(default_factory=list)
    
    fre_score: Optional[float] = None

    @property
    def color(self) -> str:
        return CATEGORY_COLORS.get(self.label, DEFAULT_CATEGORY_COLOR)

    @property
    def readability_color(self) -> str:
        """
        Returns a heatmap color based on the Flesch Reading Ease (FRE) score.
        
        Justification: FRE is a validated, widely-used metric for readability.
        Lower scores indicate higher cognitive load (complex text), while higher
        scores indicate easier to read text. This heatmap allows users to quickly
        identify which categories contain dense, complex instructions that may
        require more cognitive effort to process.
        
        Color mapping:
        - Score < 30:   Red (Very Difficult / Legal/Technical text - High cognitive load)
        - Score 30-50:  Orange (Difficult - Moderate-high cognitive load)
        - Score 50-70:  Yellow (Fairly Difficult / Plain English - Moderate load)
        - Score > 70:   Green/Blue (Easy - Low cognitive load)
        """
        if self.fre_score is None:
            return "#94a3b8"  # Gray if not calculated
            
        if self.fre_score < 30:
            return "#ef4444"  # Red - Very Difficult
        elif self.fre_score < 50:
            return "#f97316"  # Orange - Difficult
        elif self.fre_score < 70:
            return "#eab308"  # Yellow - Fairly Difficult
        else:
            return "#22c55e"  # Green - Easy

    @property
    def force_graph_radius(self) -> int:
        return 15 + min(self.count, 10)
        
    @property
    def tree_graph_radius(self) -> int:
        """
        Minimum radius: 10 (for 1 child).
        We use a slightly smaller factor to avoid breaking the tree layout, 
        but enough to make the node stand out.
        Examples with growth factor 3:
        - 1 child: 10 + 3*(0) = 10
        - 2 children: 10 + 3*(1) = 13
        - 5 children: 10 + 3*(4) = 22
        """
        base_radius = 10
        growth_factor = 3
        
        effective_children = max(1, self.count)
        
        return base_radius + (growth_factor * (effective_children - 1))

    @property
    def html_details(self) -> str:
        return f"Category: {self.label}<br>Total Rules: {self.count}"

    def inject_parent_ids(self) -> None:
        """Hydrates the leaf nodes with this category's ID to prevent global collision."""
        for rule in self.children:
            rule.parent_id = self.id

class ASTProjectInfo(BaseModel):
    """Metadata regarding the origin dataset file."""
    repoName: str
    agentsMdSource: str

class RootNode(BaseModel):
    """The root node encapsulating the entire parsed AST context."""
    id: str
    label: str
    type: Literal["root"] = "root"
    children: List[RuleCategory] = Field(default_factory=list)
    
    def hydrate_tree(self) -> None:
        for cat in self.children:
            cat.inject_parent_ids()


class AgentASTDocument(BaseModel):
    """The absolute root representation of an Extracted Agent Instruction Document."""
    projectInfo: ASTProjectInfo
    rootNode: RootNode
    thinking_process: Optional[str] = None
    
    def __init__(self, **data):
        super().__init__(**data)
        self.rootNode.hydrate_tree()

    @property
    def repo_name(self) -> str:
        return self.projectInfo.repoName

    @property
    def source_file(self) -> str:
        return self.projectInfo.agentsMdSource
        
    @property
    def root_color(self) -> str:
        return ROOT_COLOR

    @property
    def force_graph_root_radius(self) -> int:
        return 25

    @property
    def tree_graph_root_radius(self) -> int:
        return 15
        
    @property
    def root_html_details(self) -> str:
        return f"Repository Name: {self.repo_name}"
