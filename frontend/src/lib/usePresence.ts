import { useEffect, useState } from 'react';
import { useBootstrapData } from './bootstrap';
import { socket, type PresenceUser, type Status } from './presence';

export function usePresence() {
  const { user } = useBootstrapData();
  const [users, setUsers] = useState<PresenceUser[]>(socket.users);
  const [status, setStatus] = useState<Status>('connecting');
  useEffect(() => {
    const offEvents = socket.subscribe((e) => e.event === 'presence' && setUsers(e.users));
    const offStatus = socket.onStatus(setStatus);
    setUsers(socket.users);
    return () => {
      offEvents();
      offStatus();
    };
  }, []);
  return {
    users,
    online: users.filter((u) => u.status === 'online'),
    away: users.filter((u) => u.status !== 'online'),
    others: users.filter((u) => u.user_id !== user.id),
    status,
  };
}
