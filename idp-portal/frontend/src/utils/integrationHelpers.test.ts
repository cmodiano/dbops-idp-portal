/**
 * Story 31.1: Tests for integrationHelpers utility functions.
 */
import { describe, it, expect } from 'vitest';
import { integrationTypeToPlatformCode, integrationToConnector } from './integrationHelpers';

describe('integrationTypeToPlatformCode', () => {
  it('maps aap → AAP', () => {
    expect(integrationTypeToPlatformCode('aap')).toBe('AAP');
  });

  it('maps tower → Tower', () => {
    expect(integrationTypeToPlatformCode('tower')).toBe('Tower');
  });

  it('maps github_actions → GitHub Actions', () => {
    expect(integrationTypeToPlatformCode('github_actions')).toBe('GitHub Actions');
  });

  it('maps azure_devops → Azure DevOps', () => {
    expect(integrationTypeToPlatformCode('azure_devops')).toBe('Azure DevOps');
  });

  it('maps terraform → Terraform', () => {
    expect(integrationTypeToPlatformCode('terraform')).toBe('Terraform');
  });

  it('maps terraform_cloud → Terraform', () => {
    expect(integrationTypeToPlatformCode('terraform_cloud')).toBe('Terraform');
  });

  it('returns type as-is for unknown types (fallback)', () => {
    expect(integrationTypeToPlatformCode('custom_platform')).toBe('custom_platform');
  });
});

describe('integrationToConnector', () => {
  it('maps aap → aap', () => {
    expect(integrationToConnector('aap')).toBe('aap');
  });

  it('maps tower → aap (same connector)', () => {
    expect(integrationToConnector('tower')).toBe('aap');
  });

  it('maps github_actions → github_actions', () => {
    expect(integrationToConnector('github_actions')).toBe('github_actions');
  });

  it('maps azure_devops → azuredevops', () => {
    expect(integrationToConnector('azure_devops')).toBe('azuredevops');
  });

  it('maps terraform → terraform', () => {
    expect(integrationToConnector('terraform')).toBe('terraform');
  });

  it('maps terraform_cloud → terraform', () => {
    expect(integrationToConnector('terraform_cloud')).toBe('terraform');
  });

  it('returns none for unknown types', () => {
    expect(integrationToConnector('unknown')).toBe('none');
  });
});
