import React from 'react';

interface MetricCardProps {
  label: string;
  value: string | number;
  subValue?: string;
  trend?: 'up' | 'down' | 'neutral';
  className?: string;
}

export const MetricCard: React.FC<MetricCardProps> = ({ 
  label, 
  value, 
  subValue, 
  trend,
  className = '' 
}) => {
  return (
    <div className={`p-4 rounded-lg bg-card-bg border border-border shadow-md animate-slide-up ${className}`}>
      <div className="text-xs font-medium text-muted uppercase tracking-wider mb-1">
        {label}
      </div>
      <div className="flex items-baseline gap-2">
        <div className="text-2xl font-bold text-foreground">{value}</div>
        {subValue && (
          <div className={`text-sm ${
            trend === 'up' ? 'text-primary' : 
            trend === 'down' ? 'text-secondary' : 
            'text-muted'
          }`}>
            {subValue}
          </div>
        )}
      </div>
    </div>
  );
};
