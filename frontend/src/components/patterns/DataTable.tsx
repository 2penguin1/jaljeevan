import { ArrowDown, ArrowUp } from "lucide-react";
import { useMemo, useState, type ReactNode } from "react";
import { cn } from "@/lib/format";

export type Column<T> = {
  key: string;
  header: string;
  cell: (row: T) => ReactNode;
  sortValue?: (row: T) => string | number | null;
  numeric?: boolean;
  className?: string;
};

export function DataTable<T>({ caption, columns, rows, rowKey, onRowClick, initialSort }: {
  caption: string;
  columns: Column<T>[];
  rows: T[];
  rowKey: (row: T) => string;
  onRowClick?: (row: T) => void;
  initialSort?: { key: string; dir: "asc" | "desc" };
}) {
  const [sort, setSort] = useState(initialSort);
  const sorted = useMemo(() => {
    const col = columns.find((c) => c.key === sort?.key);
    if (!sort || !col?.sortValue) return rows;
    const sign = sort.dir === "asc" ? 1 : -1;
    return [...rows].sort((a, b) => {
      const x = col.sortValue!(a) ?? -Infinity;
      const y = col.sortValue!(b) ?? -Infinity;
      return (x < y ? -1 : x > y ? 1 : 0) * sign;
    });
  }, [rows, columns, sort]);

  const toggle = (col: Column<T>) =>
    setSort((s) =>
      s?.key === col.key ? { key: col.key, dir: s.dir === "asc" ? "desc" : "asc" } : { key: col.key, dir: col.numeric ? "desc" : "asc" },
    );

  return (
    <table className="w-full border-collapse text-left text-[13px]">
      <caption className="sr-only">{caption}</caption>
      <thead>
        <tr className="border-b hairline">
          {columns.map((col) => {
            const active = sort?.key === col.key;
            const Arrow = sort?.dir === "asc" ? ArrowUp : ArrowDown;
            return (
              <th
                key={col.key}
                scope="col"
                aria-sort={active ? (sort!.dir === "asc" ? "ascending" : "descending") : undefined}
                className={cn("h-9 px-3 font-normal text-text-2", col.numeric && "text-right", col.className)}
              >
                {col.sortValue ? (
                  <button
                    type="button"
                    onClick={() => toggle(col)}
                    className={cn("inline-flex items-center gap-1 hover:text-text", active && "text-text", col.numeric && "flex-row-reverse")}
                  >
                    {col.header}
                    <Arrow size={12} aria-hidden className={active ? "opacity-100" : "opacity-0"} />
                  </button>
                ) : (
                  col.header
                )}
              </th>
            );
          })}
        </tr>
      </thead>
      <tbody>
        {sorted.map((row) => (
          <tr
            key={rowKey(row)}
            onClick={onRowClick ? () => onRowClick(row) : undefined}
            className={cn("border-b hairline transition-colors duration-[var(--dur-1)]", onRowClick && "cursor-pointer hover:bg-surface")}
          >
            {columns.map((col) => (
              <td key={col.key} className={cn("h-11 px-3", col.numeric && "num text-right", col.className)}>
                {col.cell(row)}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}
