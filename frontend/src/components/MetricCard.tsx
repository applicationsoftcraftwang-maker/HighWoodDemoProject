interface Props {
  label: string;
  value: string | number | null | undefined;
  sub?: string | number | null;
  accent?: boolean;
  danger?: boolean;
  warn?: boolean;
}

const formatValue = (value: string | number | null | undefined) => {
  if (value === undefined || value === null || value === '') {
    return '—';
  }

  if (typeof value === 'number') {
    return Number.isNaN(value) ? '—' : value.toLocaleString();
  }

  return value;
};

export function MetricCard({
  label,
  value,
  sub,
  accent,
  danger,
  warn,
}: Props) {
  const className = [
    'metric-card',
    accent ? 'accent' : '',
    danger ? 'danger' : '',
    warn ? 'warn' : '',
  ]
    .filter(Boolean)
    .join(' ');

  return (
    <div className={className}>
      <div className="metric-label">{label}</div>
      <div className="metric-value">{formatValue(value)}</div>

      {sub !== undefined && sub !== null && sub !== '' ? (
        <div className="metric-sub">{formatValue(sub)}</div>
      ) : null}
    </div>
  );
}