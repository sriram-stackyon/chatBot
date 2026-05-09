interface ComparisonTableProps {
  title?: string;
  leftHeader: string;
  rightHeader: string;
  rows: Array<{
    aspect: string;
    left: string;
    right: string;
  }>;
}

export function ComparisonTable({ title, leftHeader, rightHeader, rows }: ComparisonTableProps) {
  return (
    <div className="comparison-table-container">
      {title && <div className="comparison-table-title">{title}</div>}
      <table className="comparison-table">
        <thead>
          <tr>
            <th className="comparison-table-th comparison-table-aspect">Aspect</th>
            <th className="comparison-table-th">{leftHeader}</th>
            <th className="comparison-table-th">{rightHeader}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row, idx) => (
            <tr key={idx} className={idx % 2 === 0 ? 'comparison-table-row-even' : 'comparison-table-row-odd'}>
              <td className="comparison-table-td comparison-table-aspect-cell">{row.aspect}</td>
              <td className="comparison-table-td">{row.left}</td>
              <td className="comparison-table-td">{row.right}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
