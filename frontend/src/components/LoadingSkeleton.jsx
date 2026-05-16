export function Skeleton({ className = '' }) {
  return (
    <div className={`animate-pulse bg-terminal-border/40 rounded ${className}`} />
  )
}

export function CardSkeleton() {
  return (
    <div className="card space-y-3">
      <Skeleton className="h-4 w-1/3" />
      <Skeleton className="h-8 w-1/2" />
      <Skeleton className="h-3 w-2/3" />
    </div>
  )
}

export function TableSkeleton({ rows = 5 }) {
  return (
    <div className="space-y-2">
      {Array.from({ length: rows }).map((_, i) => (
        <Skeleton key={i} className="h-8 w-full" />
      ))}
    </div>
  )
}

export function ChartSkeleton({ height = 200 }) {
  return <Skeleton className={`w-full rounded-lg`} style={{ height }} />
}
