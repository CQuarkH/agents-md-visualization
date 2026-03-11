from typing import List, Literal, Optional, Dict
from pydantic import BaseModel, Field, root_validator

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

    @property
    def color(self) -> str:
        return CATEGORY_COLORS.get(self.label, DEFAULT_CATEGORY_COLOR)

    @property
    def force_graph_radius(self) -> int:
        return 15 + min(self.count, 10)
        
    @property
    def tree_graph_radius(self) -> int:
        return 10

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
