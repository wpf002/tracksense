/**
 * Reusable dark data table.
 *
 * Props:
 *   columns: [{ key, label, className? }]
 *   rows: array of objects (keyed by column.key, or render via column.render(row))
 *   onRowClick?: (row) => void
 *   highlightKey?: value — rows whose `id` field matches will get the amber flash
 *   emptyMessage?: string
 */
export default function DataTable({
  columns,
  rows,
  onRowClick,
  highlightedRowId,
  emptyMessage = 'No data',
}) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm border-collapse">
        <thead>
          <tr className="border-b border-border bg-surface">
            {columns.map((col) => (
              <th
                key={col.key}
                className={[
                  'px-3 py-2 text-left text-xs font-semibold tracking-widest uppercase text-text-muted',
                  col.className ?? '',
                ].join(' ')}
              >
                {col.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 ? (
            <tr>
              <td
                colSpan={columns.length}
                className="px-3 py-6 text-center text-text-muted text-xs uppercase tracking-widest"
              >
                {emptyMessage}
              </td>
            </tr>
          ) : (
            rows.map((row, i) => (
              <tr
                key={row.id ?? i}
                onClick={onRowClick ? () => onRowClick(row) : undefined}
                className={[
                  'border-b border-border transition-colors',
                  onRowClick ? 'cursor-pointer hover:bg-surface-2' : '',
                  highlightedRowId != null && highlightedRowId === (row.id ?? i)
                    ? 'row-highlight'
                    : 'bg-bg',
                ].join(' ')}
              >
                {columns.map((col) => (
                  <td
                    key={col.key}
                    className={[
                      'px-3 py-2 text-text-primary',
                      col.className ?? '',
                    ].join(' ')}
                  >
                    {col.render ? col.render(row) : row[col.key]}
                  </td>
                ))}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  )
}