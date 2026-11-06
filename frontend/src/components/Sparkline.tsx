export function Sparkline({ data, width = 120, height = 32, tone }: {
  data: number[]; width?: number; height?: number; tone?: "pos" | "neg";
}) {
  if (!data || data.length < 2) return <div style={{ width, height }} />;
  const min = Math.min(...data);
  const max = Math.max(...data);
  const span = max - min || 1;
  const pts = data.map((v, i) => [(i / (data.length - 1)) * width, height - ((v - min) / span) * (height - 4) - 2]);
  const d = pts.map(([x, y], i) => `${i ? "L" : "M"}${x.toFixed(1)},${y.toFixed(1)}`).join(" ");
  const t = tone ?? (data[data.length - 1] >= data[0] ? "pos" : "neg");
  const color = t === "pos" ? "var(--color-pos)" : "var(--color-neg)";
  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} aria-hidden>
      <path d={`${d} L${width},${height} L0,${height} Z`} fill={color} opacity={0.08} />
      <path d={d} fill="none" stroke={color} strokeWidth={1.4} />
    </svg>
  );
}
