/**
 * NotificationTemplateEditor — Story 63.4
 *
 * Éditeur dédié pour les notifications send_email et send_teams.
 * Affiche des champs nommés (pas une table clé/valeur générique),
 * des templates prédéfinis, et intègre le VariablePicker sur les champs de template.
 */

import { useRef } from 'react';
import type { FC, ElementRef, RefObject } from 'react';
import { Button, Input, Space, Typography } from 'antd';
import type { InputRef } from 'antd';

import { VariablePicker } from '../workflow/VariablePicker';
import type { AvailableVariablesStep } from '../../../services/output_schema_service';

type TextAreaRef = ElementRef<typeof Input.TextArea>;

const { TextArea } = Input;
const { Text } = Typography;

export interface NotificationTemplateEditorProps {
  value: Record<string, string> | null;
  onChange: (v: Record<string, string> | null) => void;
  disabled?: boolean;
  workflowId?: number;
  currentStepId: string;
  availableStepIds?: string[];
  /** Variables locales dérivées du output_mapping des nodes en mémoire. */
  localVariables?: AvailableVariablesStep[];
  /** Story 83-10: widened to string for full declarative support via ui_hints.input_renderer */
  operation: string;
}

// Templates prédéfinis par opération
const PREDEFINED_TEMPLATES = {
  send_email: [
    {
      label: '✅ Succès',
      subject: '✅ {{ action_name }} terminé dans {{ environment }}',
      body: "Exécution {{ execution_id }} : {{ action_name }} terminé avec succès dans {{ environment }}.",
    },
    {
      label: '❌ Échec',
      subject: '❌ {{ action_name }} échoué dans {{ environment }}',
      body: "Exécution {{ execution_id }} : {{ action_name }} a échoué dans {{ environment }}.\n\nErreur : {{ steps.STEP_ID.error_summary | default('inconnu', true) }}\n\nLogs :\n{{ steps.STEP_ID.platform_logs | truncate(500) | default('aucun log', true) }}",
    },
    {
      label: '🔔 Approbation',
      subject: '🔔 Approbation requise — {{ action_name }} dans {{ environment }}',
      body: "L'exécution {{ execution_id }} de {{ action_name }} dans {{ environment }} requiert votre approbation.",
    },
  ],
  send_teams: [
    {
      label: '✅ Succès',
      title: '✅ {{ action_name }} — {{ environment }}',
      message: "Exécution {{ execution_id }} : {{ action_name }} terminé avec succès dans {{ environment }}.",
    },
    {
      label: '❌ Échec',
      title: '❌ {{ action_name }} — {{ environment }}',
      message: "Exécution {{ execution_id }} : {{ action_name }} a échoué dans {{ environment }}.\nErreur : {{ steps.STEP_ID.error_summary | default('inconnu', true) }}",
    },
    {
      label: '🔔 Approbation',
      title: '🔔 Approbation requise — {{ action_name }}',
      message: "L'exécution {{ execution_id }} de {{ action_name }} dans {{ environment }} requiert votre approbation.",
    },
  ],
};

export const NotificationTemplateEditor: FC<NotificationTemplateEditorProps> = ({
  value,
  onChange,
  disabled = false,
  workflowId,
  currentStepId,
  availableStepIds,
  localVariables,
  operation,
}) => {
  const current = value ?? {};

  const recipientRef = useRef<InputRef>(null);
  const ccRef = useRef<InputRef>(null);
  const subjectRef = useRef<InputRef>(null);
  const bodyRef = useRef<TextAreaRef>(null);
  const attachmentsRef = useRef<InputRef>(null);
  const webhookUrlRef = useRef<InputRef>(null);
  const titleRef = useRef<InputRef>(null);
  const messageRef = useRef<TextAreaRef>(null);

  const handleChange = (key: string, newVal: string) => {
    onChange({ ...current, [key]: newVal });
  };

  const insertAtCursor = (
    ref: RefObject<InputRef | TextAreaRef | null>,
    key: string,
    expression: string,
  ) => {
    const nativeEl =
      (ref.current as InputRef)?.input ??
      (ref.current as TextAreaRef)?.resizableTextArea?.textArea;
    if (!nativeEl) {
      handleChange(key, (current[key] ?? '') + expression);
      return;
    }
    const start = nativeEl.selectionStart ?? nativeEl.value.length;
    const end = nativeEl.selectionEnd ?? nativeEl.value.length;
    const newValue = nativeEl.value.slice(0, start) + expression + nativeEl.value.slice(end);
    handleChange(key, newValue);
    requestAnimationFrame(() => {
      nativeEl.focus();
      nativeEl.setSelectionRange(start + expression.length, start + expression.length);
    });
  };

  if (operation === 'send_email') {
    const templates = PREDEFINED_TEMPLATES.send_email;
    return (
      <div data-testid="notification-template-editor-email">
        <div style={{ marginBottom: 8 }}>
          <Text type="secondary" style={{ fontSize: 11 }}>
            Templates prédéfinis :
          </Text>
          <Space style={{ marginLeft: 8 }}>
            {templates.map((tpl) => (
              <Button
                key={tpl.label}
                size="small"
                disabled={disabled}
                onClick={() => onChange({ ...current, subject: tpl.subject, body: tpl.body })}
              >
                {tpl.label}
              </Button>
            ))}
          </Space>
        </div>

        <div style={{ marginBottom: 8 }}>
          <div style={{ display: 'flex', alignItems: 'center', marginBottom: 2 }}>
            <Text type="secondary" style={{ fontSize: 12, flex: 1 }}>
              Destinataire (recipient_email)
            </Text>
            <VariablePicker
              workflowId={workflowId}
              currentStepId={currentStepId}
              availableStepIds={availableStepIds}
              localVariables={localVariables}
              disabled={disabled}
              onSelect={(expr) => insertAtCursor(recipientRef, 'recipient_email', expr)}
            />
          </div>
          <Input
            ref={recipientRef}
            size="small"
            value={current.recipient_email ?? ''}
            disabled={disabled}
            onChange={(e) => handleChange('recipient_email', e.target.value)}
            placeholder="dba@company.com"
          />
        </div>

        <div style={{ marginBottom: 8 }}>
          <div style={{ display: 'flex', alignItems: 'center', marginBottom: 2 }}>
            <Text type="secondary" style={{ fontSize: 12, flex: 1 }}>
              CC (optionnel, séparé par virgule)
            </Text>
            <VariablePicker
              workflowId={workflowId}
              currentStepId={currentStepId}
              availableStepIds={availableStepIds}
              localVariables={localVariables}
              disabled={disabled}
              onSelect={(expr) => insertAtCursor(ccRef, 'cc', expr)}
            />
          </div>
          <Input
            ref={ccRef}
            size="small"
            value={current.cc ?? ''}
            disabled={disabled}
            onChange={(e) => handleChange('cc', e.target.value)}
            placeholder="admin@company.com,{{ steps.patch.output.contact_email }}"
          />
        </div>

        <div style={{ marginBottom: 8 }}>
          <div style={{ display: 'flex', alignItems: 'center', marginBottom: 2 }}>
            <Text type="secondary" style={{ fontSize: 12, flex: 1 }}>
              Sujet (subject)
            </Text>
            <VariablePicker
              workflowId={workflowId}
              currentStepId={currentStepId}
              availableStepIds={availableStepIds}
              localVariables={localVariables}
              disabled={disabled}
              onSelect={(expr) => insertAtCursor(subjectRef, 'subject', expr)}
            />
          </div>
          <Input
            ref={subjectRef}
            size="small"
            value={current.subject ?? ''}
            disabled={disabled}
            onChange={(e) => handleChange('subject', e.target.value)}
            placeholder="{{ action_name }} — {{ environment }}"
          />
        </div>

        <div style={{ marginBottom: 8 }}>
          <div style={{ display: 'flex', alignItems: 'center', marginBottom: 2 }}>
            <Text type="secondary" style={{ fontSize: 12, flex: 1 }}>
              Corps du message (body)
            </Text>
            <VariablePicker
              workflowId={workflowId}
              currentStepId={currentStepId}
              availableStepIds={availableStepIds}
              localVariables={localVariables}
              disabled={disabled}
              onSelect={(expr) => insertAtCursor(bodyRef, 'body', expr)}
            />
          </div>
          <TextArea
            ref={bodyRef}
            rows={6}
            value={current.body ?? ''}
            disabled={disabled}
            onChange={(e) => handleChange('body', e.target.value)}
            placeholder="Exécution {{ execution_id }} : {{ action_name }} terminé dans {{ environment }}."
          />
        </div>

        <div style={{ marginBottom: 8 }}>
          <div style={{ display: 'flex', alignItems: 'center', marginBottom: 2 }}>
            <Text type="secondary" style={{ fontSize: 12, flex: 1 }}>
              Pièce jointe (optionnel — chemin ou {'{{ steps.X.output.Y }}' })
            </Text>
            <VariablePicker
              workflowId={workflowId}
              currentStepId={currentStepId}
              availableStepIds={availableStepIds}
              localVariables={localVariables}
              disabled={disabled}
              onSelect={(expr) => insertAtCursor(attachmentsRef, 'attachments', expr)}
            />
          </div>
          <Input
            ref={attachmentsRef}
            size="small"
            value={current.attachments ?? ''}
            disabled={disabled}
            onChange={(e) => handleChange('attachments', e.target.value)}
            placeholder="{{ steps.patch.output.report_path }}"
          />
        </div>
      </div>
    );
  }

  // send_teams
  const templates = PREDEFINED_TEMPLATES.send_teams;
  return (
    <div data-testid="notification-template-editor-teams">
      <div style={{ marginBottom: 8 }}>
        <Text type="secondary" style={{ fontSize: 11 }}>
          Templates prédéfinis :
        </Text>
        <Space style={{ marginLeft: 8 }}>
          {templates.map((tpl) => (
            <Button
              key={tpl.label}
              size="small"
              disabled={disabled}
              onClick={() => onChange({ ...current, title: tpl.title, message: tpl.message })}
            >
              {tpl.label}
            </Button>
          ))}
        </Space>
      </div>

      <div style={{ marginBottom: 8 }}>
        <div style={{ display: 'flex', alignItems: 'center', marginBottom: 2 }}>
          <Text type="secondary" style={{ fontSize: 12, flex: 1 }}>
            Webhook URL
          </Text>
          <VariablePicker
            workflowId={workflowId}
            currentStepId={currentStepId}
            availableStepIds={availableStepIds}
            disabled={disabled}
            onSelect={(expr) => insertAtCursor(webhookUrlRef, 'webhook_url', expr)}
          />
        </div>
        <Input
          ref={webhookUrlRef}
          size="small"
          value={current.webhook_url ?? ''}
          disabled={disabled}
          onChange={(e) => handleChange('webhook_url', e.target.value)}
          placeholder="https://..."
        />
      </div>

      <div style={{ marginBottom: 8 }}>
        <div style={{ display: 'flex', alignItems: 'center', marginBottom: 2 }}>
          <Text type="secondary" style={{ fontSize: 12, flex: 1 }}>
            Titre (title)
          </Text>
          <VariablePicker
            workflowId={workflowId}
            currentStepId={currentStepId}
            availableStepIds={availableStepIds}
            disabled={disabled}
            onSelect={(expr) => insertAtCursor(titleRef, 'title', expr)}
          />
        </div>
        <Input
          ref={titleRef}
          size="small"
          value={current.title ?? ''}
          disabled={disabled}
          onChange={(e) => handleChange('title', e.target.value)}
          placeholder="[IDP Portal] {{ action_name }} — {{ environment }}"
        />
      </div>

      <div style={{ marginBottom: 8 }}>
        <div style={{ display: 'flex', alignItems: 'center', marginBottom: 2 }}>
          <Text type="secondary" style={{ fontSize: 12, flex: 1 }}>
            Message
          </Text>
          <VariablePicker
            workflowId={workflowId}
            currentStepId={currentStepId}
            availableStepIds={availableStepIds}
            disabled={disabled}
            onSelect={(expr) => insertAtCursor(messageRef, 'message', expr)}
          />
        </div>
        <TextArea
          ref={messageRef}
          rows={5}
          value={current.message ?? ''}
          disabled={disabled}
          onChange={(e) => handleChange('message', e.target.value)}
          placeholder="Exécution {{ execution_id }} : {{ action_name }} terminé dans {{ environment }}."
        />
      </div>

      <div style={{ marginBottom: 8 }}>
        <Text type="secondary" style={{ fontSize: 12 }}>
          Couleur hex (color, optionnel)
        </Text>
        <Input
          size="small"
          value={current.color ?? ''}
          disabled={disabled}
          onChange={(e) => handleChange('color', e.target.value)}
          placeholder="FF0000 (défaut: FF0000)"
          style={{ width: 160 }}
        />
      </div>
    </div>
  );
};
