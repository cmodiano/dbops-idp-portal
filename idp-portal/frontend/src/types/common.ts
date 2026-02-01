export type UserProfileType = 'dba_applicatif' | 'dba_infrastructure' | 'client_business' | 'business' | 'dbops' | 'securite';

export type NavigationTabKey = 'catalog' | 'executions' | 'dashboard' | 'admin' | 'audit';

/** Profile types considered "business" for simplified UI (Story 7.1). */
export const BUSINESS_PROFILES: UserProfileType[] = ['client_business', 'business'];

export interface User {
  id: number;
  username: string;
  display_name: string;
  profile: UserProfileType;
  navigation_tabs: NavigationTabKey[];
  /** Story 6.3: auditor role for audit log access. */
  is_auditor?: boolean;
  /** Story 7.1: backend-provided flag for business profile. */
  is_business_profile?: boolean;
}
