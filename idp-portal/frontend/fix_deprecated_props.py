#!/usr/bin/env python3
"""
Fix deprecated Ant Design props: message → title
For both notification API and Alert component
"""

import re
import sys
from pathlib import Path

# Files to fix (from code review findings)
NOTIFICATION_FILES = [
    'src/components/catalog/ExecutionWizard.tsx',
    'src/hooks/useEditExecution.ts',
    'src/hooks/useWorkflowExportImport.tsx',
    'src/components/admin/BusinessRulesPolicyPanel.tsx',
    'src/components/admin/FeatureFlagsPanel.tsx',
    'src/hooks/useExecutionRestart.ts',
    'src/pages/admin/ProfilesAdminPanel.tsx',
    'src/pages/ExecutionsPage.tsx',
    'src/components/admin/ProfileImportModal.tsx',
    'src/components/admin/analytics/AdminAnalyticsDashboard.tsx',
    'src/components/admin/IntegrationsTable.tsx',
]

ALERT_FILES = [
    'src/components/executions/ExecutionDetailDrawer.tsx',
    'src/components/admin/ProfileForm.tsx',
    'src/components/admin/ActionWizard.tsx',
    'src/pages/AuditPage.tsx',
    'src/components/workflow/WorkflowValidationAlert.tsx',
    'src/components/admin/ProfileWizard.tsx',
    'src/pages/CalendarPage.tsx',
    'src/components/admin/IntegrationForm.tsx',
    'src/components/admin/ActionPalette.tsx',
    'src/components/admin/BusinessRulePolicyModal.tsx',
]

def fix_notification_props(content: str) -> tuple[str, int]:
    """Replace notification.*({ message: with title:"""
    # Pattern: notification.(success|error|warning|info)({ message:
    pattern = r'(notification\.(success|error|warning|info)\(\{\s*)message:'
    replacement = r'\1title:'
    new_content, count = re.subn(pattern, replacement, content)
    return new_content, count

def fix_alert_props(content: str) -> tuple[str, int]:
    """Replace <Alert message= with title="""
    # Pattern: <Alert ...message=
    pattern = r'(<Alert[^>]*\s)message='
    replacement = r'\1title='
    new_content, count = re.subn(pattern, replacement, content)
    return new_content, count

def main():
    base_dir = Path(__file__).parent
    total_fixed = 0
    errors = []

    print("🔧 Fixing deprecated Ant Design props...")
    print()

    # Fix notification files
    print("📢 Fixing notification.*({{ message: → title:")
    for rel_path in NOTIFICATION_FILES:
        file_path = base_dir / rel_path
        if not file_path.exists():
            errors.append(f"❌ File not found: {rel_path}")
            continue

        content = file_path.read_text(encoding='utf-8')
        new_content, count = fix_notification_props(content)

        if count > 0:
            file_path.write_text(new_content, encoding='utf-8')
            print(f"  ✅ {rel_path}: {count} occurrences fixed")
            total_fixed += count
        else:
            print(f"  ⚠️  {rel_path}: 0 occurrences (already fixed?)")

    print()
    print("🚨 Fixing <Alert message= → title=:")
    for rel_path in ALERT_FILES:
        file_path = base_dir / rel_path
        if not file_path.exists():
            errors.append(f"❌ File not found: {rel_path}")
            continue

        content = file_path.read_text(encoding='utf-8')
        new_content, count = fix_alert_props(content)

        if count > 0:
            file_path.write_text(new_content, encoding='utf-8')
            print(f"  ✅ {rel_path}: {count} occurrences fixed")
            total_fixed += count
        else:
            print(f"  ⚠️  {rel_path}: 0 occurrences (already fixed?)")

    print()
    print("=" * 60)
    print(f"✅ Total: {total_fixed} deprecated props fixed")

    if errors:
        print()
        print("⚠️  Errors:")
        for err in errors:
            print(f"  {err}")
        return 1

    return 0

if __name__ == '__main__':
    sys.exit(main())
