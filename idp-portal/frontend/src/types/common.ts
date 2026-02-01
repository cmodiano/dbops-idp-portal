export type UserProfileType = 'dba_applicatif' | 'dba_infrastructure' | 'client_business' | 'dbops' | 'securite';

export type NavigationTabKey = 'catalog' | 'executions' | 'dashboard' | 'admin' | 'audit';

export interface User {
  id: number;
  username: string;
  display_name: string;
  profile: UserProfileType;
  navigation_tabs: NavigationTabKey[];
  /** Story 6.3: auditor role for audit log access. */
  is_auditor?: boolean;
}
