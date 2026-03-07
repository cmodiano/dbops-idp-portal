/**
 * Tests for MappingHelpPopover — Story 57.20, Task 1.
 */

import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MappingHelpPopover } from './MappingHelpPopover';

describe('MappingHelpPopover — input variant', () => {
  it('renders the help icon for input', () => {
    render(<MappingHelpPopover type="input" />);
    expect(screen.getByLabelText('Aide syntaxe input_mapping')).toBeInTheDocument();
  });

  it('shows input syntax help content on click', () => {
    render(<MappingHelpPopover type="input" />);
    fireEvent.click(screen.getByLabelText('Aide syntaxe input_mapping'));
    expect(screen.getByText('Syntaxe input_mapping')).toBeInTheDocument();
    expect(screen.getByText(/steps\.<step_id>\.<champ>/)).toBeInTheDocument();
  });

  it('shows allowed filters in input help', () => {
    render(<MappingHelpPopover type="input" />);
    fireEvent.click(screen.getByLabelText('Aide syntaxe input_mapping'));
    expect(screen.getByText('Filtres autorisés :')).toBeInTheDocument();
    expect(screen.getByText(/concatène une liste/)).toBeInTheDocument();
    expect(screen.getByText(/nombre d'éléments/)).toBeInTheDocument();
    expect(screen.getByText(/premier élément/)).toBeInTheDocument();
    expect(screen.getByText(/valeur par défaut/)).toBeInTheDocument();
  });

  it('shows concrete example in input help', () => {
    render(<MappingHelpPopover type="input" />);
    fireEvent.click(screen.getByLabelText('Aide syntaxe input_mapping'));
    expect(screen.getByText(/steps\.discovery\.databases \| join/)).toBeInTheDocument();
  });

  it('shows available steps when provided (AC4)', () => {
    const steps = [
      { value: 'step-aaa', label: 'Étape 1 — Discovery' },
      { value: 'step-bbb', label: 'Étape 2 — Deploy' },
    ];
    render(<MappingHelpPopover type="input" availableSteps={steps} />);
    fireEvent.click(screen.getByLabelText('Aide syntaxe input_mapping'));

    expect(screen.getByText('Étapes disponibles :')).toBeInTheDocument();
    expect(screen.getByText('Étape 1 — Discovery')).toBeInTheDocument();
    expect(screen.getByText('Étape 2 — Deploy')).toBeInTheDocument();
    expect(screen.getByText(/steps\.step-aaa\./)).toBeInTheDocument();
    expect(screen.getByText(/steps\.step-bbb\./)).toBeInTheDocument();
  });

  it('does not show available steps section when list is empty', () => {
    render(<MappingHelpPopover type="input" availableSteps={[]} />);
    fireEvent.click(screen.getByLabelText('Aide syntaxe input_mapping'));
    expect(screen.queryByText('Étapes disponibles :')).not.toBeInTheDocument();
  });
});

describe('MappingHelpPopover — output variant', () => {
  it('renders the help icon for output', () => {
    render(<MappingHelpPopover type="output" />);
    expect(screen.getByLabelText('Aide syntaxe output_mapping')).toBeInTheDocument();
  });

  it('shows output syntax help content on click', () => {
    render(<MappingHelpPopover type="output" />);
    fireEvent.click(screen.getByLabelText('Aide syntaxe output_mapping'));
    expect(screen.getByText('Syntaxe output_mapping')).toBeInTheDocument();
    expect(screen.getByText(/\$\.chemin\.vers\.champ/)).toBeInTheDocument();
  });

  it('mentions that $. prefix is optional', () => {
    render(<MappingHelpPopover type="output" />);
    fireEvent.click(screen.getByLabelText('Aide syntaxe output_mapping'));
    expect(screen.getByText(/optionnel/)).toBeInTheDocument();
  });

  it('shows typical outputs for platform step_type (AC3)', () => {
    render(<MappingHelpPopover type="output" stepType="platform" />);
    fireEvent.click(screen.getByLabelText('Aide syntaxe output_mapping'));
    expect(screen.getByText('child_execution_id')).toBeInTheDocument();
    expect(screen.getByText('referenced_action_id')).toBeInTheDocument();
    expect(screen.getByText('child_status')).toBeInTheDocument();
  });

  it('shows typical outputs for service_call step_type (AC3)', () => {
    render(<MappingHelpPopover type="output" stepType="service_call" />);
    fireEvent.click(screen.getByLabelText('Aide syntaxe output_mapping'));
    expect(screen.getByText('number')).toBeInTheDocument();
    expect(screen.getByText('sys_id')).toBeInTheDocument();
  });

  it('shows typical outputs for http_request step_type (AC3)', () => {
    render(<MappingHelpPopover type="output" stepType="http_request" />);
    fireEvent.click(screen.getByLabelText('Aide syntaxe output_mapping'));
    expect(screen.getByText('body')).toBeInTheDocument();
    expect(screen.getByText('status_code')).toBeInTheDocument();
  });

  it('does not show typical outputs for unknown step_type', () => {
    render(<MappingHelpPopover type="output" stepType="evaluation" />);
    fireEvent.click(screen.getByLabelText('Aide syntaxe output_mapping'));
    expect(screen.queryByText('Champs de sortie typiques :')).not.toBeInTheDocument();
  });

  it('mentions that outputs are accessible via steps template', () => {
    render(<MappingHelpPopover type="output" />);
    fireEvent.click(screen.getByLabelText('Aide syntaxe output_mapping'));
    expect(screen.getByText(/steps\.<step_id>\.<champ_extrait>/)).toBeInTheDocument();
  });
});
