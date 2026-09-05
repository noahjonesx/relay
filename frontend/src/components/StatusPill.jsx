const VARIANTS = {
  idle:    { icon: "○", label: "Idle",    className: "muted" },
  running: { icon: "●", label: "Running", className: "accent" },
  good:    { icon: "●", label: "Done",    className: "good" },
  critical:{ icon: "●", label: "Failed",  className: "critical" },
};

export default function StatusPill({ variant, label }) {
  const v = VARIANTS[variant] || VARIANTS.idle;
  return (
    <span className={`status-pill status-pill--${v.className}`}>
      <span aria-hidden="true">{v.icon}</span>
      {label || v.label}
    </span>
  );
}
