interface Props {
  isError: boolean;
  isStale: boolean;
}

export function ConnectionBanner({ isError, isStale }: Props) {
  if (!isError && !isStale) return null;

  return (
    <div className={`banner ${isError ? 'error' : 'stale'}`}>
      {isError
        ? 'API is currently unreachable. The dashboard will keep retrying automatically.'
        : 'Data may be stale. Showing cached values while the next refresh completes.'}
    </div>
  );
}
