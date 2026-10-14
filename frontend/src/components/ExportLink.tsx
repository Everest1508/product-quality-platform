import { apiUrl } from '@/lib/env';
import { DownloadIcon } from '@/components/ui/icons';
import { Button } from '@/components/ui/button';

// A plain link to a CSV the server builds; the session cookie authorises it, so nothing is fetched into the page.
export function ExportLink({ path, label = 'Export CSV' }: { path: string; label?: string }) {
  const url = `${apiUrl('/ui-api/v1/')}${path}${path.includes('?') ? '&' : '?'}export=csv`;
  return <Button asChild variant="outline" size="sm"><a href={url} download><DownloadIcon />{label}</a></Button>;
}
