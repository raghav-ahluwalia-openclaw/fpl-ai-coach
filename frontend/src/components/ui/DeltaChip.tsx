import React from 'react';

interface DeltaChipProps {
  value: number | string;
  label?: string;
  trend?: 'up' | 'down' | 'neutral';
  showIcon?: boolean;
}

export const DeltaChip: React.FC<DeltaChipProps> = ({ 
  value, 
  label, 
  trend = 'neutral',
  showIcon = true 
}) => {
  const isPositive = trend === 'up';
  const isNegative = trend === 'down';

  const colorClass = isPositive 
    ? 'bg-primary/10 text-primary border-primary/20' 
    : isNegative 
    ? 'bg-secondary/10 text-secondary border-secondary/20' 
    : 'bg-muted/10 text-muted border-muted/20';

  return (
    <div className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold border ${colorClass} transition-all duration-fast`}>
      {showIcon && (
        <span className="text-[10px]">
          {isPositive ? '▲' : isNegative ? '▼' : '●'}
        </span>
      )}
      <span>{value}{label && ` ${label}`}</span>
    </div>
  );
};
