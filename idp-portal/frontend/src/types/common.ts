export type UserProfileType = 'dba_applicatif' | 'dba_infrastructure' | 'client_business' | 'dbops' | 'securite';

export type NavigationTabKey = 'catalog' | 'executions' | 'dashboard' | 'admin';

export interface User {
  id: number;
  username: string;
  display_name: string;
  profile: UserProfileType;
  navigation_tabs: NavigationTabKey[];
}
