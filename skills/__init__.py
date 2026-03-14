"""Skills module - Claude Skill definitions and helpers."""

# This module contains skill definitions for Claude Code
# Skills are documented in .md files and invoked via prompts

SKILL_DEFINITIONS = {
    'file-processor': {
        'description': 'Process files dropped into the vault, analyze content, categorize, and create action plans',
        'trigger': 'Files in /Processing/ with type file_drop',
        'output_folders': ['/Done/', '/Plans/', '/Pending_Approval/']
    },
    'email-triage': {
        'description': 'Process incoming emails, categorize, prioritize, and draft responses',
        'trigger': 'Files in /Processing/ with type email',
        'output_folders': ['/Done/', '/Approved/', '/Plans/']
    },
    'invoice-generator': {
        'description': 'Generate invoices from project data and send for approval',
        'trigger': 'Invoice requests or project completion',
        'output_folders': ['/Invoices/', '/Pending_Approval/']
    },
    'dashboard-updater': {
        'description': 'Update the main dashboard with current statistics and status',
        'trigger': 'Periodic or after significant events',
        'output_folders': []
    }
}

def get_skill_description(skill_name: str) -> str:
    """Get description for a skill."""
    skill = SKILL_DEFINITIONS.get(skill_name)
    if skill:
        return skill['description']
    return "Unknown skill"

def get_all_skills() -> dict:
    """Get all skill definitions."""
    return SKILL_DEFINITIONS.copy()
