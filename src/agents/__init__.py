"""
Agent module exports for the AI Project Management System.
"""

from src.agents.simple_agent import SimpleAgent  # New LangChain-based agent

# Optional legacy imports that will be phased out
__legacy_agents__ = {}

try:
    from src.agents.chat_coordinator import ChatCoordinatorAgent
    __legacy_agents__["chat_coordinator"] = ChatCoordinatorAgent
except ImportError:
    pass

try:
    from src.agents.project_manager import ProjectManagerAgent
    __legacy_agents__["project_manager"] = ProjectManagerAgent
except ImportError:
    pass

try:
    from src.agents.research_specialist import ResearchSpecialistAgent
    __legacy_agents__["research_specialist"] = ResearchSpecialistAgent
except ImportError:
    pass

try:
    from src.agents.business_analyst import BusinessAnalystAgent
    __legacy_agents__["business_analyst"] = BusinessAnalystAgent
except ImportError:
    pass

try:
    from src.agents.code_developer import CodeDeveloperAgent
    __legacy_agents__["code_developer"] = CodeDeveloperAgent
except ImportError:
    pass

try:
    from src.agents.code_reviewer import CodeReviewerAgent
    __legacy_agents__["code_reviewer"] = CodeReviewerAgent
except ImportError:
    pass

try:
    from src.agents.report_drafter import ReportDrafterAgent
    __legacy_agents__["report_drafter"] = ReportDrafterAgent
except ImportError:
    pass

try:
    from src.agents.report_reviewer import ReportReviewerAgent
    __legacy_agents__["report_reviewer"] = ReportReviewerAgent
except ImportError:
    pass

try:
    from src.agents.report_publisher import ReportPublisherAgent
    __legacy_agents__["report_publisher"] = ReportPublisherAgent
except ImportError:
    pass

try:
    from src.agents.request_parser import RequestParserAgent
    __legacy_agents__["request_parser"] = RequestParserAgent
except ImportError:
    pass