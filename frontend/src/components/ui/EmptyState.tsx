import React from 'react';

interface EmptyStateProps {
  title?: string;
  description?: string;
  icon?: React.ReactNode;
  action?: React.ReactNode;
  className?: string;
}

export const EmptyState: React.FC<EmptyStateProps> = ({ 
  title = 'No Data Available', 
  description = 'There is nothing to show at the moment.',
  icon,
  action,
  className = '' 
}) => {
  return (
    <div className={`flex flex-col items-center justify-center p-12 text-center rounded-xl bg-card-bg/10 border-2 border-dashed border-border/20 ${className} animate-fade-in`}>
      {icon && <div className="mb-4 text-muted">{icon}</div>}
      <h3 className="text-lg font-semibold text-foreground mb-1">{title}</h3>
      <p className="text-sm text-muted max-w-xs mx-auto mb-6">
        {description}
      </p>
      {action && <div>{action}</div>}
    </div>
  );
};
