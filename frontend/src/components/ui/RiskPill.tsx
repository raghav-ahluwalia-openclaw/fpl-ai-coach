import React from 'react';

type RiskLevel = 'low' | 'medium' | 'high' | 'critical';

interface RiskPillProps {
  level: RiskLevel;
  className?: string;
}

const riskConfig: Record<RiskLevel, { label: string; colorClass: string }> = {
  low: { label: 'Low Risk', colorClass: 'bg-primary/20 text-primary border-primary/30' },
  medium: { label: 'Medium Risk', colorClass: 'bg-yellow-400/20 text-yellow-400 border-yellow-400/30' },
  high: { label: 'High Risk', colorClass: 'bg-secondary/20 text-secondary border-secondary/30' },
  critical: { label: 'Critical', colorClass: 'bg-red-600/20 text-red-600 border-red-600/40 animate-pulse' },
};

export const RiskPill: React.FC<RiskPillProps> = ({ level, className = '' }) => {
  const { label, colorClass } = riskConfig[level];

  return (
    <div className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold border ${colorClass} ${className}`}>
      {label}
    </div>
  );
};
