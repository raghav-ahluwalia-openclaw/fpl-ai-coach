import React from 'react';

interface ConfidenceMeterProps {
  score: number; // 0 to 100
  label?: string;
}

export const ConfidenceMeter: React.FC<ConfidenceMeterProps> = ({ 
  score, 
  label = 'AI Confidence' 
}) => {
  const getProgressColor = () => {
    if (score >= 80) return 'bg-primary shadow-glow';
    if (score >= 50) return 'bg-yellow-400';
    return 'bg-secondary';
  };

  return (
    <div className="space-y-1.5 w-full">
      <div className="flex justify-between text-[11px] font-bold uppercase tracking-wider text-muted">
        <span>{label}</span>
        <span className="text-foreground">{score}%</span>
      </div>
      <div className="h-2 w-full bg-border rounded-full overflow-hidden">
        <div 
          className={`h-full ${getProgressColor()} transition-all duration-slow ease-decelerate`}
          style={{ width: `${score}%` }}
        />
      </div>
    </div>
  );
};
