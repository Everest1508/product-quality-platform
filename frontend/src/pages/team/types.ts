export type Member = {
  id: number;
  user: { id: number; username: string; name: string; email: string; discord_id: string; initial: string; first_name: string; last_name: string };
  role: string;
  role_label: string;
  is_leave_approver: boolean;
  joined: string;
  can_edit: boolean;
  can_remove: boolean;
  is_you: boolean;
};

export type TeamResponse = {
  items: Member[];
  page: { number: number; num_pages: number; count: number; per_page: number };
  counts: { total: number; owner_admin: number; developer: number; support_viewer: number };
  roles: [string, string][];
  assignable_roles: [string, string][];
  can_manage: boolean;
};

export type AddInput = { username: string; email: string; first_name: string; last_name: string; password: string; role: string };
export type EditInput = { first_name: string; last_name: string; email: string; discord_id: string; role: string; is_leave_approver: boolean };
